#!/usr/bin/env python3
"""Execute clock/MAC MMIO helpers and reject broadened network RAM profiles."""
import argparse
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from ethernet_net_profile import ethernet_net_profile, NETWORK_NODES
from inspect_images import parse_fdt

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
#define ETH_HLEN 14
#define ETH_FCS_LEN 4
#define MAX_FRAME_SIZE 1600
static u32 control[5], port[256], global[128];
static void *pointers[5];
static unsigned int mode, writes, delays;
static u32 readl(void *address)
{
    if (address == &control[0]) {
        if (mode == 1 && writes == 1) return 0x1b;
        if (mode == 2 && writes == 2) return 0;
    }
    return *(u32 *)address;
}
static void writel(u32 value, void *address)
{
    writes++;
    *(u32 *)address = value;
}
#define mdelay(ms) do { assert((ms) == 5); delays++; } while (0)
#define usleep_range(low, high) do { \
    assert((low) == 1000 && (high) == 10000); delays++; } while (0)
#include "ty1208z-ethernet-gate.h"
#include "hi3798mv100-femac.h"
static void initialize(void)
{
    const u32 expected[] = {3, 0x101, 0x0e000004, 0x03000001, 8};
    for (unsigned int i = 0; i < 5; i++) {
        control[i] = expected[i]; pointers[i] = &control[i];
    }
    writes = delays = 0;
}
int main(void)
{
    for (unsigned int field = 0; field < 5; field++) {
        for (unsigned int bit = 0; bit < 32; bit++) {
            initialize(); control[field] ^= BIT(bit);
            assert(ty1208z_ethernet_gate_enable(pointers) == -ENODEV);
            assert(!writes && !delays);
        }
    }
    initialize();
    assert(!ty1208z_ethernet_gate_enable(pointers));
    assert(writes == 1 && delays == 1 && control[0] == 0xb);
    assert(!ty1208z_ethernet_gate_disable(pointers[0]));
    assert(writes == 2 && control[0] == 3);
    initialize(); mode = 1;
    assert(ty1208z_ethernet_gate_enable(pointers) == -EIO);
    assert(writes == 1 && !delays);
    mode = 0; initialize(); control[0] = 0x1b;
    assert(ty1208z_ethernet_gate_disable(pointers[0]) == -EBUSY);
    assert(!writes);
    initialize(); assert(!ty1208z_ethernet_gate_enable(pointers)); mode = 2;
    assert(ty1208z_ethernet_gate_disable(pointers[0]) == -EIO);
    mode = 0;
    for (unsigned int i = 0; i < 256; i++) port[i] = 0xa5a5a5a5;
    for (unsigned int i = 0; i < 128; i++) global[i] = 0x5a5a5a5a;
    writes = delays = 0;
    hi3798mv100_femac_setup(port, global);
    assert(writes == 4 && !delays);
    for (unsigned int i = 0; i < 256; i++) {
        u32 expected = 0xa5a5a5a5;
        if (i == 0x218 / 4) expected &= ~GENMASK(25, 23);
        if (i == 0x210 / 4) expected &= ~BIT(18);
        if (i == 0x380 / 4) expected &= ~BIT(14);
        assert(port[i] == expected); /* Includes untouched 0x340. */
    }
    for (unsigned int i = 0; i < 128; i++) {
        u32 expected = 0x5a5a5a5a;
        if (i == 0x18 / 4) expected |= 3;
        assert(global[i] == expected);
    }
    writes = delays = 0;
    hi3798mv100_femac_reset(global);
    assert(writes == 4 && delays == 4 && global[2] == (0x5a5a5a5a & ~1U));
    for (u32 length = 0; length < 4096; length++)
        assert(hi3798mv100_femac_valid_length(length) == (length >= 18 && length <= 1600));
    puts("ETHERNET_NET_HELPERS_PASS: state mutations, restoration, exact setup, reset, all lengths");
    return 0;
}
"""


def execute_helpers():
    with tempfile.TemporaryDirectory(prefix="ethernet-net-") as directory:
        build = Path(directory)
        (build / "linux").mkdir()
        for name in ("delay.h", "io.h"):
            (build / "linux" / name).write_text("/* MMIO supplied by harness. */\n")
        (build / "linux/errno.h").write_text(
            "#define ENODEV 19\n#define EBUSY 16\n#define EIO 5\n")
        (build / "test.c").write_text(HARNESS)
        binary = build / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        "-I", str(build), "-I", str(ROOT / "overlay/drivers/clk/hisilicon"),
                        "-I", str(ROOT / "overlay/drivers/net/ethernet/hisilicon"),
                        str(build / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = ('CONFIG_LOCALVERSION="-ty1208z-ethernet-net1"\n' +
                       ''.join(f"CONFIG_{name}=y\n" for name in (
                           "TY1208Z_ETHERNET_INHERITED", "NET", "INET", "PACKET", "NETDEVICES",
                           "HISI_FEMAC", "MDIO_HISI_FEMAC", "PHYLIB", "FESTA_TY1208Z_PHY")))
        nodes = {path: {} for path in (
            "/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
            "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
            "/soc/timer@f8a29000", "/soc/serial@f8b00000", *sorted(NETWORK_NODES))}
        nodes["/"] = {"compatible": {"strings": ["tianyi,ty1208z-ca-diagnostic", "hi3798mv100-series"]}}
        nodes["/soc/clock-controller@f8a220cc"] = {
            "compatible": {"strings": ["tianyi,ty1208z-inherited-ethernet-clock"]},
            "reg": {"cells": [0xf8a220cc, 4, 0xf8a22120, 4, 0xf8a20008, 4, 0xf8a20118, 4, 0xf8a20844, 4]},
            "#clock-cells": {"cells": [0]}, "phandle": {"cells": [2]}}
        nodes["/soc/mdio@f9841100"] = {
            "compatible": {"strings": ["hisilicon,hisi-femac-mdio"]},
            "reg": {"cells": [0xf9841100, 8]}, "clocks": {"cells": [2]},
            "#address-cells": {"cells": [1]}, "#size-cells": {"cells": [0]}}
        nodes["/soc/mdio@f9841100/ethernet-phy@1"] = {
            "compatible": {"strings": ["ethernet-phy-id2066.9823"]},
            "reg": {"cells": [1]}, "phandle": {"cells": [3]}}
        nodes["/soc/ethernet@f9840000"] = {
            "compatible": {"strings": ["hisilicon,hi3798mv100-femac-inherited"]},
            "reg": {"cells": [0xf9840000, 0x400, 0xf9841300, 0x200]},
            "interrupts": {"cells": [0, 71, 4]}, "clocks": {"cells": [2]},
            "phy-mode": {"strings": ["mii"]}, "phy-handle": {"cells": [3]}}
        self.tree = {"nodes": [{"path": path, "properties": props} for path, props in nodes.items()]}

    def test_exact_profile(self):
        self.assertTrue(ethernet_net_profile(self.tree, self.config))

    def test_each_property_change(self):
        for index, node in enumerate(self.tree["nodes"]):
            if node["path"] not in NETWORK_NODES:
                continue
            for key in node["properties"]:
                tree = copy.deepcopy(self.tree)
                value = tree["nodes"][index]["properties"][key]
                kind = next(iter(value))
                value[kind] = ["changed"] if kind == "strings" else [0xdeadbeef]
                with self.subTest(path=node["path"], key=key), self.assertRaises(ValueError):
                    ethernet_net_profile(tree, self.config)

    def test_no_reset_gpio_or_extra_nodes(self):
        for key in ("resets", "reset-gpios", "status", "mac-address"):
            tree = copy.deepcopy(self.tree)
            tree["nodes"][-1]["properties"][key] = {"cells": [1]}
            with self.assertRaises(ValueError):
                ethernet_net_profile(tree, self.config)
        self.tree["nodes"].append({"path": "/soc/usb@1", "properties": {}})
        with self.assertRaises(ValueError):
            ethernet_net_profile(self.tree, self.config)

    def test_cannot_broaden_existing_diagnostic(self):
        with self.assertRaises(ValueError):
            ethernet_net_profile(self.tree, self.config.replace("CONFIG_TY1208Z_ETHERNET_INHERITED=y\n", ""))
        for name in ("BLOCK", "MMC", "NETFILTER", "USB_SUPPORT", "MODULES", "SMP", "DEBUG_FS",
                     "HI3798MV100_ETHERNET_CLOCK_ID", "HI3798MV100_ETHERNET_AUDIT"):
            with self.subTest(option=name), self.assertRaises(ValueError):
                ethernet_net_profile(self.tree, self.config + f"CONFIG_{name}=y\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    execute_helpers()
    if args.artifacts:
        tree = parse_fdt((args.artifacts / "ty1208z-diagnostic.dtb").read_bytes())
        ethernet_net_profile(tree, (args.artifacts / "linux.config").read_text())
        subprocess.run(["qemu-arm", str(args.artifacts / "busybox.armhf"), "--list"],
                       stdout=subprocess.PIPE, check=True)
    unittest.main(argv=[__file__], verbosity=2)
