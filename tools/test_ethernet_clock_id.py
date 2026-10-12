#!/usr/bin/env python3
"""Execute the real volatile clock/PHY helper with guarded fake MMIO."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from ethernet_profiles import ethernet_clock_id_profile
import test_ethernet_audit

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define __iomem
#define BIT(x) (1U << (x))
static u32 crg, mdio[2];
static unsigned int mode, clock_writes, mdio_writes, data_reads, polls, delays;
static u32 fake_readl(void *address)
{
    if (address == &crg) {
        if (mode == 7 && clock_writes == 1) return 0x1b;
        if (mode == 8 && mdio_writes == 2) return 0x2b;
        if (mode == 9 && clock_writes == 2) return 0;
        return crg;
    }
    assert(clock_writes == 1 && crg == 0xb && delays == 1);
    if (address == &mdio[1]) {
        assert(mdio_writes == data_reads + 1);
        data_reads++;
        if (mode == 5) return 0;
        if (mode == 6) return 0xffffffff;
        return 0xa5a50000 | (data_reads == 1 ? 0x2066 : 0x9901);
    }
    assert(address == &mdio[0]);
    polls++;
    assert(polls <= 4004);
    if ((mode == 1 && mdio_writes == 0) || (mode == 2 && mdio_writes == 1)
            || (mode == 3 && mdio_writes == 1 && data_reads == 1)
            || (mode == 4 && mdio_writes == 2)) return 0;
    return BIT(15);
}
static void fake_writel(u32 value, void *address)
{
    if (address == &crg) {
        assert(clock_writes < 2);
        assert(value == (clock_writes == 0 ? 0xbU : 3U));
        clock_writes++;
        crg = value;
        return;
    }
    assert(address == &mdio[0] && clock_writes == 1 && delays == 1);
    assert(mdio_writes < 2);
    assert(value == (mdio_writes == 0 ? 0x102U : 0x103U));
    mdio_writes++;
}
#define readl(address) fake_readl(address)
#define writel(value, address) fake_writel(value, address)
#define mdelay(msecs) do { assert((msecs) == 5); delays++; } while (0)
#define readl_poll_timeout(address, value, condition, delay, timeout) ({ \
    assert((delay) == 1 && (timeout) == 1000); \
    int rc = -ETIMEDOUT; unsigned int elapsed = 0; \
    do { value = readl(address); if (condition) { rc = 0; break; } \
    } while (++elapsed <= (timeout)); rc; })
#include "ty1208z-ethernet-clock-id.h"
static void initialize(void)
{
    crg = 3;
    clock_writes = mdio_writes = data_reads = polls = delays = 0;
}
int main(void)
{
    struct ty1208z_eth_clock_result result;
    u32 state[] = { 0x101, 0x0e000004, 0x03000001, 8 };
    unsigned int field, bit;
    for (field = 0; field < 5; field++) {
        for (bit = 0; bit < 32; bit++) {
            u32 changed[4];
            int ret;
            initialize();
            for (unsigned int i = 0; i < 4; i++) changed[i] = state[i];
            if (field == 0) crg ^= BIT(bit); else changed[field - 1] ^= BIT(bit);
            ret = ty1208z_eth_clock_id(&crg, mdio, changed[0], changed[1],
                                      changed[2], changed[3], &result);
            assert(ret == -ENODEV && !result.changed && !result.restore_verified);
            assert(clock_writes == 0 && mdio_writes == 0 && polls == 0);
        }
    }
    for (mode = 0; mode <= 9; mode++) {
        int ret;
        initialize();
        ret = ty1208z_eth_clock_id(&crg, mdio, state[0], state[1],
                                  state[2], state[3], &result);
        assert(result.before == 3 && result.changed);
        if (mode == 0) {
            assert(ret == 0 && result.phy_id == 0x20669901);
        } else if (mode < 5) {
            assert(ret == -ETIMEDOUT && result.phy_id == 0);
        } else if (mode < 7) {
            assert(ret == -ENODEV && result.phy_id == 0);
        } else {
            assert(ret == (mode == 8 ? -EBUSY : -EIO));
        }
        if (mode <= 6) {
            assert(clock_writes == 2 && crg == 3 && result.restored == 3);
            assert(result.restore_verified && delays == 1);
        } else {
            assert(!result.restore_verified);
            assert(clock_writes == (mode == 9 ? 2U : 1U));
            if (mode == 7) assert(mdio_writes == 0 && delays == 0);
        }
    }
    puts("ETHERNET_CLOCK_ID_PROTOCOL_PASS: exact guards, bit-only writes, MDIO faults, restoration");
    return 0;
}
"""


def execute_protocol():
    header = ROOT / "overlay/drivers/soc/hisilicon/ty1208z-ethernet-clock-id.h"
    with tempfile.TemporaryDirectory(prefix="ethernet-clock-id-test-") as directory:
        build = Path(directory)
        (build / "linux").mkdir()
        for name in ("bitops.h", "io.h", "iopoll.h", "delay.h"):
            (build / "linux" / name).write_text("/* MMIO seam defined by the harness. */\n")
        (build / "linux/errno.h").write_text(
            "#define ETIMEDOUT 110\n#define ENODEV 19\n#define EIO 5\n#define EBUSY 16\n")
        (build / "test.c").write_text(HARNESS)
        binary = build / "test"
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O1", "-g",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        "-I", str(build), "-I", str(header.parent), str(build / "test.c"),
                        "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


class ClockProfileTests(test_ethernet_audit.ProfileTests):
    def setUp(self):
        super().setUp()
        self.tree = copy.deepcopy(self.tree)
        node = self.tree["nodes"][0]
        node["path"] = "/soc/ethernet-clock-id@f9841100"
        node["properties"]["compatible"]["strings"] = ["tianyi,ty1208z-ethernet-clock-id"]
        node["properties"]["reg"]["cells"][:2] = [0xf9841100, 8]
        node["properties"]["reg-names"]["strings"][0] = "mdio"
        self.config = ('CONFIG_LOCALVERSION="-ty1208z-ethernet-clock-id1"\n'
                       'CONFIG_HI3798MV100_ETHERNET_CLOCK_ID=y\n')
        self.validator = ethernet_clock_id_profile

    def test_inherited_audit_cannot_share_this_profile(self):
        with self.assertRaises(ValueError):
            self.validator(self.tree, self.config + "CONFIG_HI3798MV100_ETHERNET_AUDIT=y\n")


if __name__ == "__main__":
    execute_protocol()
    unittest.main(verbosity=2)
