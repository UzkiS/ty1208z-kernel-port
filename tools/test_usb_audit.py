#!/usr/bin/env python3
"""Execute actual read-only USB snapshot helper and reject profile mutations."""
import argparse
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from inspect_images import parse_fdt
from usb_audit_profile import usb_audit_profile, RESOURCES

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define __iomem
#define BIT(x) (1U << (x))
#define GENMASK(h, l) (((~0U) >> (31 - (h))) & ((~0U) << (l)))
static u32 values[5], ehci[3], ohci;
static void *control[5];
static unsigned int reads;
static u32 readl(void *address)
{
    if (reads < 5) {
        assert(address == &values[reads]);
    } else {
        assert(reads < 9);
        assert(address == (reads < 8 ? &ehci[reads - 5] : &ohci));
        assert(values[0] == 0x7f && values[1] == 3 && values[2] == 8);
    }
    reads++;
    return *(u32 *)address;
}
#define writel(value, address) assert(!"USB audit must not write registers")
#include "ty1208z-usb-audit.h"
static void initialize(void)
{
    const u32 original[] = {0x7f, 3, 8, 0xb01c, 0x37980110};
    for (unsigned int i = 0; i < 5; i++) {
        values[i] = original[i]; control[i] = &values[i];
    }
    ehci[0] = 0x01000010; ehci[1] = 0x12; ehci[2] = 0x00000080; ohci = 0x10;
    reads = 0;
}
int main(void)
{
    for (unsigned int field = 0; field < 4; field++) {
        for (unsigned int bit = 0; bit < 32; bit++) {
            struct ty1208z_usb_snapshot state = {0};
            initialize();
            /* Only mutations in required control bits must inhibit MMIO.
             * PHY test-data/reserved bits are observed, never interpreted.
             */
            u32 mask = field == 0 ? 0x3707f : field == 1 ? 0xf03 :
                       field == 2 ? 0x209 : 0;
            if (!(mask & BIT(bit))) continue;
            values[field] ^= BIT(bit);
            ty1208z_usb_observe(control, ehci, &ohci, &state);
            assert(!state.controller_read && reads == 5);
        }
    }
    for (unsigned int mode = 0; mode < 2; mode++) {
        struct ty1208z_usb_snapshot state = {0};
        initialize(); values[4] = mode ? 0xffffffff : 0;
        ty1208z_usb_observe(control, ehci, &ohci, &state);
        assert(!state.controller_read && reads == 5);
    }
    struct ty1208z_usb_snapshot state = {0};
    initialize();
    ty1208z_usb_observe(control, ehci, &ohci, &state);
    assert(state.controller_read && reads == 9);
    assert(state.crg46 == values[0] && state.crg47 == values[1]);
    assert(state.usb0 == values[2] && state.usb1 == values[3] && state.sysid0 == values[4]);
    assert(state.ehci_capbase == ehci[0] && state.ehci_hcsparams == ehci[1]);
    assert(state.ehci_hccparams == ehci[2] && state.ohci_revision == ohci);
    puts("USB_AUDIT_HELPER_PASS: exact ordered reads, inactive clocks/resets, invalid revision, no writes");
    return 0;
}
"""


def execute_helper():
    with tempfile.TemporaryDirectory(prefix="usb-audit-") as directory:
        path = Path(directory)
        (path / "linux").mkdir()
        for name in ("bitops.h", "io.h", "types.h"):
            (path / "linux" / name).write_text("/* MMIO/types supplied by the harness. */\n")
        (path / "test.c").write_text(HARNESS)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I", str(path),
                        "-I", str(ROOT / "overlay/drivers/soc/hisilicon"),
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        paths = ("/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
                 "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
                 "/soc/timer@f8a29000", "/soc/serial@f8b00000", "/soc/usb-audit@f9890000")
        self.tree = {"nodes": [{"path": path, "properties": {}} for path in paths]}
        self.tree["nodes"][0]["properties"] = {"compatible": {"strings": [
            "tianyi,ty1208z-ca-diagnostic", "hi3798mv100-series"]}}
        self.tree["nodes"][-1]["properties"] = {
            "compatible": {"strings": ["tianyi,ty1208z-usb-register-audit"]},
            "reg": {"cells": RESOURCES.copy()}}
        self.config = 'CONFIG_LOCALVERSION="-ty1208z-usb-audit1"\nCONFIG_HI3798MV100_USB_AUDIT=y\n'

    def test_exact_profile(self):
        self.assertTrue(usb_audit_profile(self.tree, self.config))

    def test_every_resource_cell_is_fixed(self):
        for index in range(len(RESOURCES)):
            tree = copy.deepcopy(self.tree)
            tree["nodes"][-1]["properties"]["reg"]["cells"][index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                usb_audit_profile(tree, self.config)

    def test_foreign_identity_peripherals_and_subsystems_rejected(self):
        with self.assertRaises(ValueError):
            usb_audit_profile(self.tree, self.config.replace("-ty1208z-usb-audit1", "-ty1208z-diag1"))
        for option in ("USB_SUPPORT", "NET", "MMC", "BLOCK", "MTD", "DEBUG_FS", "MODULES", "SMP",
                       "HI3798MV100_EMMC_AUDIT", "HI3798MV100_ETHERNET_AUDIT"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                usb_audit_profile(self.tree, self.config + f"CONFIG_{option}=y\n")
        tree = copy.deepcopy(self.tree)
        tree["nodes"].append({"path": "/soc/ehci@f9930000", "properties": {}})
        with self.assertRaises(ValueError):
            usb_audit_profile(tree, self.config)
        for property_name in ("interrupts", "clocks", "resets"):
            tree = copy.deepcopy(self.tree)
            tree["nodes"][-1]["properties"][property_name] = {"cells": [1]}
            with self.subTest(property_name=property_name), self.assertRaises(ValueError):
                usb_audit_profile(tree, self.config)
        with self.assertRaises(ValueError):
            usb_audit_profile(self.tree, self.config.replace("CONFIG_HI3798MV100_USB_AUDIT=y\n", ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    execute_helper()
    if args.artifacts:
        tree = parse_fdt((args.artifacts / "ty1208z-diagnostic.dtb").read_bytes())
        if not usb_audit_profile(tree, (args.artifacts / "linux.config").read_text()):
            raise ValueError("Compiled USB audit profile is absent")
    unittest.main(argv=[__file__], verbosity=2)
