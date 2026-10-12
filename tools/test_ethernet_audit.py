#!/usr/bin/env python3
"""Execute real bounded PHY-ID helper under sanitizers and test profile gates."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from ethernet_profiles import ethernet_audit_profile

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define __iomem
#define BIT(x) (1U << (x))
static u32 registers[2];
static unsigned int mode, writes, data_reads, polls;
static u32 fake_readl(void *address)
{
    if (address == &registers[1]) {
        assert(writes == data_reads + 1);
        data_reads++;
        if (mode == 5) return 0;
        if (mode == 6) return 0xffffffff;
        return 0xa5a50000 | (data_reads == 1 ? 0x2066 : 0x9901);
    }
    assert(address == &registers[0]);
    polls++;
    assert(polls <= 4004);
    if ((mode == 1 && writes == 0) || (mode == 2 && writes == 1)
            || (mode == 3 && writes == 1 && data_reads == 1)
            || (mode == 4 && writes == 2)) return 0;
    return BIT(15);
}
static void fake_writel(u32 value, void *address)
{
    assert(address == &registers[0]);
    assert(writes < 2);
    assert(value == (writes == 0 ? 0x102U : 0x103U));
    assert(!(value & (BIT(13) | BIT(15))));
    writes++;
}
#define readl(address) fake_readl(address)
#define writel(value, address) fake_writel(value, address)
/* Simulate bounded polling at the MMIO seam, retaining the real condition. */
#define readl_poll_timeout(address, value, condition, delay, timeout) ({ \
    assert((delay) == 1 && (timeout) == 1000); \
    int rc = -ETIMEDOUT; unsigned int elapsed = 0; \
    do { value = readl(address); if (condition) { rc = 0; break; } \
    } while (++elapsed <= (timeout)); rc; })
#include "ty1208z-ethernet-audit.h"
int main(void)
{
    unsigned int mac, phy, select, addr;
    for (mac = 0; mac < 32; mac++)
        for (phy = 0; phy < 32; phy++)
            for (select = 0; select <= 1; select++)
                for (addr = 0; addr < 32; addr++) {
                    bool expected = (mac & 0x1b) == 0xb && (phy & 0x11) == 1
                        && select == 0 && addr == 1;
                    assert(ty1208z_eth_inherited_ready(mac, phy, select << 8, addr) == expected);
                }
    for (mode = 0; mode <= 6; mode++) {
        u32 id = 0x12345678;
        int ret;
        writes = data_reads = polls = 0;
        ret = ty1208z_eth_read_phy_id(registers, &id);
        if (mode == 0) {
            assert(ret == 0 && id == 0x20669901);
            assert(writes == 2 && data_reads == 2);
        } else {
            assert(ret == (mode < 5 ? -ETIMEDOUT : -ENODEV));
            assert(id == 0x12345678);
            assert(writes == (mode == 1 ? 0U : mode <= 3 ? 1U : 2U));
            assert(data_reads == (mode <= 2 ? 0U : mode <= 4 ? 1U : 2U));
        }
    }
    puts("ETHERNET_AUDIT_PROTOCOL_PASS: fixed PHY/register reads, readiness, busy timeouts, invalid IDs");
    return 0;
}
"""


def execute_protocol():
    header = ROOT / "overlay/drivers/soc/hisilicon/ty1208z-ethernet-audit.h"
    with tempfile.TemporaryDirectory(prefix="ethernet-audit-test-") as directory:
        build = Path(directory)
        (build / "linux").mkdir()
        for name in ("bitops.h", "io.h", "iopoll.h"):
            (build / "linux" / name).write_text("/* MMIO seam defined by the harness. */\n")
        (build / "linux/errno.h").write_text("#define ETIMEDOUT 110\n#define ENODEV 19\n")
        (build / "test.c").write_text(HARNESS)
        binary = build / "test"
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O1", "-g",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        "-I", str(build), "-I", str(header.parent), str(build / "test.c"),
                        "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tree = {"nodes": [{"path": "/soc/ethernet-audit@f9840000", "properties": {
            "compatible": {"strings": ["tianyi,ty1208z-ethernet-audit"]},
            "reg": {"cells": [0xf9840000, 0x4000, 0xf8a220cc, 4, 0xf8a22120, 4,
                              0xf8a20008, 4, 0xf8a20118, 4, 0xf8a20844, 4]},
            "reg-names": {"strings": ["mac", "crg51", "phy-crg", "phy-select", "phy-address", "phy-ldo"]},
        }}]}
        self.config = 'CONFIG_LOCALVERSION="-ty1208z-ethernet-audit1"\nCONFIG_HI3798MV100_ETHERNET_AUDIT=y\n'

    def test_exact_profile_and_plain_profile(self):
        self.assertTrue(ethernet_audit_profile(self.tree, self.config))
        self.assertFalse(ethernet_audit_profile({"nodes": []}, ""))

    def test_no_node_without_explicit_profile(self):
        with self.assertRaises(ValueError):
            ethernet_audit_profile(self.tree, "")

    def test_changed_and_duplicate_resources_are_rejected(self):
        for index in range(12):
            tree = copy.deepcopy(self.tree)
            tree["nodes"][0]["properties"]["reg"]["cells"][index] += 4
            with self.assertRaises(ValueError):
                ethernet_audit_profile(tree, self.config)
        tree = copy.deepcopy(self.tree)
        tree["nodes"] += tree["nodes"]
        with self.assertRaises(ValueError):
            ethernet_audit_profile(tree, self.config)

    def test_unreviewed_properties_and_subsystems_are_rejected(self):
        tree = copy.deepcopy(self.tree)
        tree["nodes"][0]["properties"]["interrupts"] = {"cells": [0, 71, 4]}
        with self.assertRaises(ValueError):
            ethernet_audit_profile(tree, self.config)
        tree = copy.deepcopy(self.tree)
        tree["nodes"][0]["properties"]["reg-names"]["strings"].reverse()
        with self.assertRaises(ValueError):
            ethernet_audit_profile(tree, self.config)
        for option in ("BLOCK", "MMC", "NET", "MODULES", "SMP", "MTD", "USB_SUPPORT",
                       "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT", "DEBUG_FS"):
            with self.assertRaises(ValueError):
                ethernet_audit_profile(self.tree, self.config + f"CONFIG_{option}=y\n")


if __name__ == "__main__":
    execute_protocol()
    unittest.main(verbosity=2)
