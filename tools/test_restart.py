#!/usr/bin/env python3
"""Execute the actual SP805 helpers with MMIO traps and profile mutations."""
import argparse
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from inspect_images import parse_fdt
from restart_profile import NODE, restart_profile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define __iomem
static u32 registers[1024];
static unsigned int reads, writes;
static u32 readl(void *address)
{
    unsigned int offset = (u32 *)address - registers;
    assert(offset < 1024);
    if (writes) {
        assert(writes == 4 && offset == 0xc00 / 4);
    } else {
        assert(reads < 9);
        unsigned int expected = reads < 4 ? 0xfe0 / 4 + reads :
                                reads < 8 ? 0xff0 / 4 + reads - 4 : 0x008 / 4;
        assert(offset == expected);
    }
    reads++;
    return registers[offset];
}
static void writel(u32 value, void *address)
{
    const u32 offsets[] = {0xc00, 0x008, 0x000, 0x008};
    const u32 values[] = {0x1acce551, 0, 0x100, 3};
    assert(reads == 9 && writes < 4);
    assert((u32 *)address - registers == offsets[writes] / 4);
    assert(value == values[writes]);
    registers[offsets[writes] / 4] = value;
    writes++;
}
#include "ty1208z-sp805-restart.h"
static void initialize(u32 pid, u32 cid, u32 control)
{
    for (unsigned int i = 0; i < 1024; i++) registers[i] = 0;
    for (unsigned int i = 0; i < 4; i++) {
        registers[0xfe0 / 4 + i] = (pid >> (i * 8)) & 0xff;
        registers[0xff0 / 4 + i] = (cid >> (i * 8)) & 0xff;
    }
    registers[0x008 / 4] = control;
    reads = writes = 0;
}
int main(void)
{
    struct ty1208z_sp805_state state;
    initialize(0x00141805, 0xb105f00d, 0);
    ty1208z_sp805_observe(registers, &state);
    assert(reads == 9 && writes == 0 && ty1208z_sp805_restart_ready(&state));
    assert(state.peripheral_id == 0x00141805 && state.cell_id == 0xb105f00d);
    for (unsigned int bit = 0; bit < 32; bit++) {
        if (bit < 24) {
            initialize(0x00141805 ^ (1U << bit), 0xb105f00d, 0);
            assert(!ty1208z_sp805_restart(registers) && reads == 9 && !writes);
        }
        initialize(0x00141805, 0xb105f00d ^ (1U << bit), 0);
        assert(!ty1208z_sp805_restart(registers) && reads == 9 && !writes);
        initialize(0x00141805, 0xb105f00d, 1U << bit);
        assert(!ty1208z_sp805_restart(registers) && reads == 9 && !writes);
    }
    for (u32 control = 1; control <= 3; control++) {
        initialize(0x00141805, 0xb105f00d, control);
        assert(!ty1208z_sp805_restart(registers) && !writes);
    }
    for (unsigned int revision = 0; revision < 256; revision++) {
        initialize(0x00141805 | revision << 24, 0xb105f00d, 0);
        assert(ty1208z_sp805_restart(registers) && reads == 10 && writes == 4);
    }
    puts("SP805_RESTART_HELPER_PASS: read-only observe, identity/control gates, exact writes and flush");
    return 0;
}
"""


def execute_helper():
    with tempfile.TemporaryDirectory(prefix="sp805-restart-") as directory:
        path = Path(directory)
        (path / "linux").mkdir()
        for name in ("io.h", "types.h"):
            (path / "linux" / name).write_text("/* Harness supplies MMIO/types. */\n")
        (path / "test.c").write_text(HARNESS)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I", str(path),
                        "-I", str(ROOT / "overlay/drivers/power/reset"),
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


class RestartTests(unittest.TestCase):
    def setUp(self):
        paths = ("/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
                 "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
                 "/soc/timer@f8a29000", "/soc/serial@f8b00000", NODE)
        self.tree = {"nodes": [{"path": path, "properties": {}} for path in paths]}
        self.tree["nodes"][0]["properties"] = {"compatible": {"strings": [
            "tianyi,ty1208z-ca-diagnostic", "hi3798mv100-series"]}}
        self.tree["nodes"][-1]["properties"] = {
            "compatible": {"strings": ["tianyi,ty1208z-sp805-restart"]},
            "reg": {"cells": [0xf8a2c000, 0x1000]}}
        self.config = ('CONFIG_LOCALVERSION="-ty1208z-restart1"\nCONFIG_POWER_RESET=y\n'
                       'CONFIG_POWER_RESET_TY1208Z_SP805=y\n')

    def test_explicit_profile(self):
        self.assertTrue(restart_profile(self.tree, self.config))
        self.assertTrue(restart_profile(self.tree, self.config + "CONFIG_POWER_RESET_HISI=y\n"))
        self.assertFalse(restart_profile({"nodes": []}, ""))
        with self.assertRaises(ValueError):
            restart_profile(self.tree, "")

    def test_resources_and_id_override_are_rejected(self):
        for index in range(2):
            tree = copy.deepcopy(self.tree)
            tree["nodes"][-1]["properties"]["reg"]["cells"][index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                restart_profile(tree, self.config)
        tree = copy.deepcopy(self.tree)
        tree["nodes"][-1]["properties"]["arm,primecell-periphid"] = {"cells": [0x00141805]}
        with self.assertRaises(ValueError):
            restart_profile(tree, self.config)

    def test_subsystems_peripherals_and_foreign_identity_are_rejected(self):
        for option in ("WATCHDOG", "USB_SUPPORT", "NET", "MMC", "BLOCK", "MTD", "SMP", "MODULES",
                       "POWER_RESET_SYSCON"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                restart_profile(self.tree, self.config + f"CONFIG_{option}=y\n")
        for original, replacement in (("-ty1208z-restart1", "-ty1208z-diag1"),
                                      ("CONFIG_POWER_RESET=y\n", "")):
            with self.assertRaises(ValueError):
                restart_profile(self.tree, self.config.replace(original, replacement))
        tree = copy.deepcopy(self.tree)
        tree["nodes"].append({"path": "/soc/watchdog@f8a2d000", "properties": {}})
        with self.assertRaises(ValueError):
            restart_profile(tree, self.config)
        tree = copy.deepcopy(self.tree)
        tree["nodes"].append({"path": "/soc/sysctrl@f8000000", "properties": {
            "compatible": {"strings": ["hisilicon,sysctrl"]}}})
        with self.assertRaises(ValueError):
            restart_profile(tree, self.config + "CONFIG_POWER_RESET_HISI=y\n")
        tree = copy.deepcopy(self.tree)
        tree["nodes"][0]["properties"]["compatible"]["strings"][0] = "other,board"
        with self.assertRaises(ValueError):
            restart_profile(tree, self.config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    execute_helper()
    if args.artifacts:
        tree = parse_fdt((args.artifacts / "ty1208z-diagnostic.dtb").read_bytes())
        if not restart_profile(tree, (args.artifacts / "linux.config").read_text()):
            raise ValueError("Compiled restart profile is absent")
    unittest.main(argv=[__file__], verbosity=2)
