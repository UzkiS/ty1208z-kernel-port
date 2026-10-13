#!/usr/bin/env python3
"""Reject widened SD read-only profiles and validate actual built RAM placement."""
import argparse
import copy
from pathlib import Path
import unittest

from inspect_images import parse_fdt
from sd_ro_profile import sd_ro_profile, CONFIG, OPTIONS
from sd_ident_profile import BASE_PATHS, NODE, RESTART, PROPERTIES, RESTART_PROPERTIES, sd_ident_profile
from test_sd_ident_profile import check_built as check_ident_built


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tree = {"nodes": [{"path": path, "properties": {}} for path in sorted(BASE_PATHS | {NODE, RESTART})]}
        props = {n["path"]: n["properties"] for n in self.tree["nodes"]}
        props["/"]["compatible"] = {"strings": ["tianyi,ty1208z-ca-sd-ro-ram", "hi3798mv100-series"]}
        props[NODE].update(copy.deepcopy(PROPERTIES))
        props[RESTART].update(copy.deepcopy(RESTART_PROPERTIES))
        self.config = CONFIG + "CONFIG_MMC_BLOCK_MINORS=16\n" + "".join(f"CONFIG_{name}=y\n" for name in sorted(OPTIONS))

    def test_required_options_and_denied_subsystems(self):
        self.assertTrue(sd_ro_profile(self.tree, self.config))
        self.assertFalse(sd_ident_profile(self.tree, self.config))
        for name in OPTIONS:
            with self.subTest(missing=name), self.assertRaises(ValueError):
                sd_ro_profile(self.tree, self.config.replace(f"CONFIG_{name}=y\n", ""))
        for name in ("MMC_DW_HI3798MV100_IDENT", "NET", "WATCHDOG", "BLK_DEV", "BLK_DEV_LOOP",
                     "POWER_RESET_TY1208Z_SP805", "PM", "PWRSEQ_SIMPLE", "MODULES", "USB_SUPPORT",
                     "BTRFS_FS", "FS_ENCRYPTION"):
            with self.subTest(enabled=name), self.assertRaises(ValueError):
                sd_ro_profile(self.tree, self.config + f"CONFIG_{name}=y\n")
        with self.assertRaises(ValueError):
            sd_ro_profile(self.tree, self.config.replace("MINORS=16", "MINORS=8"))

    def test_exact_identity_resources_and_peripherals(self):
        for path in (NODE, RESTART):
            for field in (PROPERTIES if path == NODE else RESTART_PROPERTIES):
                changed = copy.deepcopy(self.tree)
                props = next(n["properties"] for n in changed["nodes"] if n["path"] == path)
                del props[field]
                with self.subTest(path=path, field=field), self.assertRaises(ValueError):
                    sd_ro_profile(changed, self.config)
        changed = copy.deepcopy(self.tree)
        changed["nodes"].append({"path": "/soc/emmc@f9830000", "properties": {}})
        with self.assertRaises(ValueError):
            sd_ro_profile(changed, self.config)
        with self.assertRaises(ValueError):
            sd_ro_profile(self.tree, self.config.replace("sd-ro1", "sd-ident1"))
        changed = copy.deepcopy(self.tree)
        changed["nodes"][0]["properties"]["compatible"]["strings"][0] = "tianyi,ty1208z-ca-sd-ident-ram"
        with self.assertRaises(ValueError):
            sd_ro_profile(changed, self.config)


def check_built(artifacts):
    assert sd_ro_profile(parse_fdt((artifacts / "ty1208z-diagnostic.dtb").read_bytes()),
                         (artifacts / "linux.config").read_text())
    # Reuse the identical exact-image/fresh-inspection RAM planner fixture.
    check_ident_built(artifacts, sd_ro_profile)
    print("SD_RO_RAM_PLAN_PASS: exact read-only block/filesystem identity, CRC and low-memory placement")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    if args.artifacts:
        check_built(args.artifacts)
    unittest.main(argv=[__file__], verbosity=2)
