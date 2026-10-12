#!/usr/bin/env python3
"""Reject weakened profile gates using real built DT/configuration inputs."""
import copy
from pathlib import Path
import unittest

from emmc_profiles import identification_profile
from inspect_images import parse_fdt

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        artifact = ROOT / "artifacts/emmc-ident1"
        self.tree = parse_fdt((artifact / "ty1208z-diagnostic.dtb").read_bytes())
        self.config = (artifact / "linux.config").read_text()

    def test_actual_identification_config_passes(self):
        self.assertTrue(identification_profile(self.tree, self.config))

    def test_unreviewed_subsystems_are_rejected(self):
        for option in ("MMC_BLOCK", "MMC_TEST", "MMC_DW_HI3798CV200", "BLOCK", "DEBUG_FS",
                       "PWRSEQ_EMMC", "NET", "MODULES"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                identification_profile(self.tree, self.config + f"CONFIG_{option}=y\n")

    def test_weakened_dt_constraints_are_rejected(self):
        for field, value in (("bus-width", 8), ("max-frequency", 100000000),
                             ("fifo-depth", 128), ("clock-frequency", 50000000)):
            tree = copy.deepcopy(self.tree)
            props = next(node["properties"] for node in tree["nodes"] if node["path"] == "/soc/mmc@f9830000")
            props[field] = {"cells": [value]}
            with self.subTest(field=field), self.assertRaises(ValueError):
                identification_profile(tree, self.config)

    def test_unreviewed_properties_are_rejected(self):
        for field in ("clocks", "resets", "cap-mmc-highspeed", "mmc-pwrseq", "vmmc-supply"):
            tree = copy.deepcopy(self.tree)
            props = next(node["properties"] for node in tree["nodes"] if node["path"] == "/soc/mmc@f9830000")
            props[field] = {"cells": [1]}
            with self.subTest(field=field), self.assertRaises(ValueError):
                identification_profile(tree, self.config)

    def test_ordinary_diagnostic_does_not_allow_mmc(self):
        artifact = ROOT / "artifacts/diag1"
        tree = parse_fdt((artifact / "ty1208z-diagnostic.dtb").read_bytes())
        config = (artifact / "linux.config").read_text()
        self.assertFalse(identification_profile(tree, config))
        with self.assertRaises(ValueError):
            identification_profile(self.tree, config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
