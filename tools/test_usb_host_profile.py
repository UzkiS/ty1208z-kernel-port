#!/usr/bin/env python3
"""Reject resource/clock/driver mutations in the actual offline host0 image."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from inspect_images import parse_fdt
from prepare_ram_boot import prepare
from usb_host_profile import usb_host_profile

ROOT = Path(__file__).resolve().parents[1]


class HostProfileTests(unittest.TestCase):
    artifacts = ROOT / "artifacts/usb-host1"

    def setUp(self):
        self.tree = parse_fdt((self.artifacts / "ty1208z-diagnostic.dtb").read_bytes())
        self.config = (self.artifacts / "linux.config").read_text()

    def test_actual_profile(self):
        self.assertTrue(usb_host_profile(self.tree, self.config))

    def test_every_host_cell_string_and_extra_property(self):
        for index, node in enumerate(self.tree["nodes"]):
            if node["path"] not in (
                    "/soc/clock-controller@f8a220b8", "/soc/usb@f9890000", "/soc/usb@f9880000"):
                continue
            for key, value in node["properties"].items():
                # parse_fdt represents zero cells as both empty strings and
                # cells; type selection must follow the DT property.
                kind = "strings" if key == "compatible" else "cells"
                for cell in range(len(value[kind])):
                    tree = copy.deepcopy(self.tree)
                    target = tree["nodes"][index]["properties"][key][kind]
                    target[cell] = target[cell] + "-foreign" if kind == "strings" else target[cell] ^ 1
                    with self.subTest(path=node["path"], key=key, cell=cell), self.assertRaises(ValueError):
                        usb_host_profile(tree, self.config)
            tree = copy.deepcopy(self.tree)
            tree["nodes"][index]["properties"]["extra"] = {"cells": [1]}
            with self.assertRaises(ValueError):
                usb_host_profile(tree, self.config)

    def test_no_storage_class_drivers_or_other_profiles(self):
        for option in ("USB_STORAGE", "USB_UAS", "USB_SERIAL", "USB_GADGET", "USB_HID",
                       "USB_ACM", "USB_TEST", "USB_DEFAULT_PERSIST", "BLOCK", "MMC", "MTD",
                       "NET", "PM", "MODULES", "SMP", "DEBUG_FS", "TY1208Z_ETHERNET_INHERITED",
                       "HI3798MV100_USB_AUDIT", "POWER_RESET_TY1208Z_SP805"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                usb_host_profile(self.tree, self.config + f"CONFIG_{option}=y\n")
        for option in ("USB", "USB_EHCI_HCD_PLATFORM", "USB_OHCI_HCD_PLATFORM"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                usb_host_profile(self.tree, self.config.replace(f"CONFIG_{option}=y\n", ""))
            with self.subTest(module=option), self.assertRaises(ValueError):
                usb_host_profile(self.tree, self.config.replace(f"CONFIG_{option}=y\n", f"CONFIG_{option}=m\n"))
        for change in ("identity", "memory", "extra-node"):
            tree = copy.deepcopy(self.tree)
            props = {node["path"]: node["properties"] for node in tree["nodes"]}
            if change == "identity":
                props["/"]["compatible"]["strings"][0] = "tianyi,ty1208z-ca-diagnostic"
            elif change == "memory":
                props["/memory@0"]["reg"]["cells"][1] *= 2
            else:
                tree["nodes"].append({"path": "/soc/usb@f9930000", "properties": {}})
            with self.subTest(change=change), self.assertRaises(ValueError):
                usb_host_profile(tree, self.config)
        with self.assertRaises(ValueError):
            usb_host_profile(self.tree, self.config.replace("-ty1208z-usb-host1", "-ty1208z-diag1"))

    def test_built_image_has_no_ram_boot_permission(self):
        raw = (b"Fastboot 3.3.0-dirty (vendor)\n"
               b"DDR free region baseaddr:0x1000000 size:0x3F000000\n"
               b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\n"
               b"loady [ off ] [ baud ]\ncrc32 address count [addr]\nbootm [addr [arg ...]]\n")
        with tempfile.TemporaryDirectory(prefix="usb-host-denied-") as directory:
            path = Path(directory)
            (path / "inspection.rx").write_bytes(raw)
            record = path / "inspection.json"
            record.write_text(json.dumps({"stop_reason": "probe-complete", "raw_file": "inspection.rx",
                                          "raw_sha256": hashlib.sha256(raw).hexdigest()}))
            with self.assertRaisesRegex(ValueError, "offline-only pending physical USB"):
                prepare(self.artifacts, record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts/usb-host1")
    args = parser.parse_args()
    HostProfileTests.artifacts = args.artifacts
    unittest.main(argv=[__file__], verbosity=2)
