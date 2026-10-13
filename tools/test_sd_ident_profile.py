#!/usr/bin/env python3
"""Reject modified SD resource/subsystem/restart profiles and check real RAM plan."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from inspect_images import parse_fdt
from prepare_ram_boot import prepare
from sd_ident_profile import (sd_ident_profile, NODE, RESTART, CONFIG, OPTIONS,
                              PROPERTIES, RESTART_PROPERTIES, BASE_PATHS)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tree = {"nodes": [{"path": path, "properties": {}} for path in sorted(BASE_PATHS | {NODE, RESTART})]}
        props = {n["path"]: n["properties"] for n in self.tree["nodes"]}
        props["/"]["compatible"] = {"strings": ["tianyi,ty1208z-ca-sd-ident-ram", "hi3798mv100-series"]}
        props[NODE].update(copy.deepcopy(PROPERTIES))
        props[RESTART].update(copy.deepcopy(RESTART_PROPERTIES))
        self.config = CONFIG + "".join(f"CONFIG_{name}=y\n" for name in sorted(OPTIONS))

    def test_exact_profile_and_mutations(self):
        self.assertTrue(sd_ident_profile(self.tree, self.config))
        for name in OPTIONS:
            with self.subTest(missing=name), self.assertRaises(ValueError):
                sd_ident_profile(self.tree, self.config.replace(f"CONFIG_{name}=y\n", ""))
        for name in ("MMC_BLOCK", "MMC_DW_HI3798MV100_IDENT", "BLOCK", "NET", "WATCHDOG",
                     "POWER_RESET_TY1208Z_SP805", "PM", "PWRSEQ_SIMPLE", "MODULES", "USB_SUPPORT"):
            with self.subTest(enabled=name), self.assertRaises(ValueError):
                sd_ident_profile(self.tree, self.config + f"CONFIG_{name}=y\n")
        for path in (NODE, RESTART):
            for field in (PROPERTIES if path == NODE else RESTART_PROPERTIES):
                for mutation in ("missing", "changed"):
                    changed = copy.deepcopy(self.tree)
                    props = next(n["properties"] for n in changed["nodes"] if n["path"] == path)
                    if mutation == "missing":
                        del props[field]
                    elif "cells" in props[field]:
                        props[field]["cells"][0] ^= 1
                    elif "strings" in props[field]:
                        props[field]["strings"][0] += "-foreign"
                    else:
                        props["vmmc-supply"] = {"cells": [1]}
                    with self.subTest(path=path, field=field, mutation=mutation), self.assertRaises(ValueError):
                        sd_ident_profile(changed, self.config)
        changed = copy.deepcopy(self.tree)
        changed["nodes"].append({"path": "/soc/other", "properties": {}})
        with self.assertRaises(ValueError):
            sd_ident_profile(changed, self.config)
        with self.assertRaises(ValueError):
            sd_ident_profile(self.tree, self.config.replace("sd-ident1", "diag1"))


def check_built(artifacts):
    assert sd_ident_profile(parse_fdt((artifacts / "ty1208z-diagnostic.dtb").read_bytes()),
                            (artifacts / "linux.config").read_text())
    raw = (b"Fastboot 3.3.0-dirty (vendor)\nDDR free region baseaddr:0x1000000 size:0x3F000000\n"
           b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\n"
           b"loady [ off ] [ baud ]\ncrc32 address count [addr]\nbootm [addr [arg ...]]\n")
    with tempfile.TemporaryDirectory(prefix="sd-ident-plan-") as directory:
        path = Path(directory)
        (path / "inspection.rx").write_bytes(raw)
        (path / "inspection.json").write_text(json.dumps({"stop_reason": "probe-complete", "raw_file": "inspection.rx",
                                                         "raw_sha256": hashlib.sha256(raw).hexdigest()}))
        plan = prepare(artifacts, path / "inspection.json")
    assert not plan["persistent_writes"] and "additional_loads" not in plan
    print("SD_IDENT_RAM_PLAN_PASS: actual DT/config/reset and bounded CRC/layout gate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    if args.artifacts:
        check_built(args.artifacts)
    unittest.main(argv=[__file__], verbosity=2)
