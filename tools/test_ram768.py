#!/usr/bin/env python3
"""Actual memory-probe/reset helpers and fail-closed memory/profile/evidence mutations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from inspect_images import parse_fdt
from prepare_ram_boot import prepare
from ram768_profile import BASE, NODE, IDENTITY, RESOURCES, ALLOCATIONS, END, ram768_profile, memory_boot_evidence
from test_sd_restart import HARNESS, MAIN

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ('CONFIG_LOCALVERSION="-ty1208z-ram768"\nCONFIG_POWER_RESET_TY1208Z_MV100_RAM=y\n'
          'CONFIG_HI3798MV100_TIMER=y\nCONFIG_POWER_RESET=y\nCONFIG_PROC_PAGE_MONITOR=y\nCONFIG_TMPFS=y\n')


def fixture():
    props = {name: {} for name in BASE | {NODE}}
    props["/"]["compatible"] = {"strings": IDENTITY.copy()}
    props["/memory@0"]["reg"] = {"cells": [0, END]}
    props[NODE] = {"compatible": {"strings": ["tianyi,ty1208z-mv100-ram-restart"]},
                   "reg": {"cells": [0xf8a2c000, 0x1000, 0xf8000ee0, 4]}}
    for node, fields in RESOURCES.items():
        props[node].update({field: {"cells": cells.copy()} for field, cells in fields.items()})
    return {"nodes": [{"path": path, "properties": values} for path, values in props.items()]}


def boot_fixture(path, raw=None):
    if raw is None:
        raw = (b"Bootrom start\nCPU:           Hi3798Mv100 (CA)\nDDR Size:      1GB\n"
               b"Free  Addr:          0x3E507000\n" + b"".join(
                   f"    0x{address:08X}  {size}\n".encode() for address, size in ALLOCATIONS))
    path.with_suffix(".rx").write_bytes(raw)
    path.write_text(json.dumps({"status": "restart-bootloader-verified", "restart_sent": True,
                               "persistent_writes": False, "port": "COM9",
                               "ended_utc": "2026-10-14T01:00:00+00:00",
                               "raw_sha256": hashlib.sha256(raw).hexdigest()}))
    return raw


class ProfileTests(unittest.TestCase):
    def test_peripherals_and_memory(self):
        tree = fixture()
        self.assertTrue(ram768_profile(tree, CONFIG))
        for node, properties in RESOURCES.items():
            for field in properties:
                changed = copy.deepcopy(tree)
                target = next(item["properties"] for item in changed["nodes"] if item["path"] == node)
                target[field]["cells"][0] += 1
                with self.subTest(node=node, field=field), self.assertRaises(ValueError):
                    ram768_profile(changed, CONFIG)
        for option in ("NET", "BLOCK", "MMC", "HIGHMEM", "MODULES", "SMP", "DEBUG_FS", "WATCHDOG",
                       "POWER_RESET_TY1208Z_SP805", "HI3798MV100_SD_AUDIT", "TY1208Z_ROUTER_RAM768"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                ram768_profile(tree, CONFIG + f"CONFIG_{option}=y\n")
        for field in ("compatible", "reg"):
            changed = copy.deepcopy(tree)
            props = next(item["properties"] for item in changed["nodes"] if item["path"] == NODE)
            props.pop(field)
            with self.assertRaises(ValueError):
                ram768_profile(changed, CONFIG)
        with self.assertRaises(ValueError):
            ram768_profile(tree, CONFIG.replace("ram768", "diag1"))
        with self.assertRaises(ValueError):
            ram768_profile(tree, "")

    def test_fresh_loader_allocations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "restart.json"
            original = boot_fixture(path)
            good = {"port": "COM9", "started_utc": "2026-10-14T01:00:01+00:00"}
            self.assertEqual(memory_boot_evidence(path, good), hashlib.sha256(original).hexdigest())
            for old, new in ((b"1GB", b"2GB"), (b"3E507000", b"2E507000"),
                             (b"4194304", b"4194305"), (b"(CA)", b"(other)")):
                boot_fixture(path, original.replace(old, new))
                with self.assertRaises(ValueError):
                    memory_boot_evidence(path, good)
            boot_fixture(path)
            path.with_suffix(".rx").write_bytes(original + b"foreign")
            with self.assertRaises(ValueError):
                memory_boot_evidence(path, good)
            boot_fixture(path)
            for started in ("2026-10-14T00:59:59+00:00", "2026-10-14T01:02:01+00:00"):
                with self.assertRaises(ValueError):
                    memory_boot_evidence(path, {**good, "started_utc": started})


def actual_functions():
    source = (ROOT / "overlay/drivers/power/reset/ty1208z-mv100-ram-restart.c").read_text()
    function = source[source.index("static int ty1208z_ram768_restart_callback("):
                      source.index("static const struct of_device_id")]
    harness = HARNESS.replace("ty1208z_sd_restart", "ty1208z_ram768_restart").replace(
        'ro_mode ? "tianyi,ty1208z-ca-sd-ro-ram" : "tianyi,ty1208z-ca-sd-ident-ram"',
        '"tianyi,ty1208z-ca-ram768"')
    main = MAIN.replace("ty1208z_sd_restart", "ty1208z_ram768_restart").replace(
        "SD_RESTART_PROBE_PASS", "RAM768_RESTART_PROBE_PASS")
    probe = (ROOT / "tools/ram768-probe.c").read_text()
    helpers = probe[:probe.index("int main(void)")]
    probe_main = r'''
#include <assert.h>
int main(void) {
    uint64_t minimum = UINT64_MAX, maximum = 0, high = 0;
    for (unsigned pfn = 0; pfn <= 0x40000000 / PAGE_BYTES; pfn++) {
        int result = check_entry((1ULL << 63) | pfn, &minimum, &maximum, &high);
        assert((result == 0) == (pfn >= 0x01000000 / PAGE_BYTES && pfn < 0x30000000 / PAGE_BYTES));
        assert(check_entry(pfn, &minimum, &maximum, &high) != 0);
        assert(check_entry((1ULL << 63) | (1ULL << 62) | pfn, &minimum, &maximum, &high) != 0);
    }
    assert(minimum == 4096 && maximum == 196607 && high == 131072);
    for (uint32_t word = 0; word < TEST_BYTES / sizeof(uint32_t); word += 17) {
        assert(pattern(word, 1) == ~pattern(word, 0));
        assert(pattern(word, 0) != pattern(word ^ (1U << 26), 0));
    }
    puts("RAM768_ACTUAL_PROBE_HELPERS_PASS patterns, present/swapped/redacted PFNs and every physical boundary");
}
'''
    with tempfile.TemporaryDirectory(prefix="ram768-functions-") as directory:
        path = Path(directory)
        for name, text in (("restart", harness + function + main), ("probe", helpers + probe_main)):
            file = path / (name + ".c")
            file.write_text(text)
            binary = path / name
            subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-pie", "-no-pie", str(file),
                            "-o", str(binary)], check=True)
            subprocess.run([binary], check=True)


def actual_init_memory(linuxsrc):
    source = (linuxsrc / "arch/arm/mm/init.c").read_text()
    function = source[source.index("void free_initmem(void)"):
                      source.index("#ifdef CONFIG_BLK_DEV_INITRD", source.index("void free_initmem(void)"))]
    assert "RAM768_INIT_MEMORY_RETAINED low-16MiB-reservation" in function
    harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
static unsigned board;
static bool integrator, cintegrator;
#ifndef CONFIG_POWER_RESET_TY1208Z_MV100_RAM
#define CONFIG_POWER_RESET_TY1208Z_MV100_RAM 0
#endif
#ifndef CONFIG_TY1208Z_ROUTER_RAM768
#define CONFIG_TY1208Z_ROUTER_RAM768 0
#endif
#ifndef CONFIG_TY1208Z_ROUTER_SD_RO
#define CONFIG_TY1208Z_ROUTER_SD_RO 0
#endif
#define IS_ENABLED(x) (x)
static unsigned fixed, poisoned, freed, retained;
static char init_area[16];
#define __init_begin init_area
#define __init_end (init_area + sizeof(init_area))
#define machine_is_integrator() integrator
#define machine_is_cintegrator() cintegrator
static bool __attribute__((unused)) of_machine_is_compatible(const char *name) {
    if (!strcmp(name, "tianyi,ty1208z-ca-ram768")) return board == 1;
    if (!strcmp(name, "tianyi,ty1208z-ca-openwrt-router768-ram")) return board == 2;
    assert(!strcmp(name, "tianyi,ty1208z-ca-openwrt-sdro-ram")); return board == 3;
}
#define pr_info(...) retained++
static void fix_kernmem_perms(void) { fixed++; }
static void poison_init_mem(void *start, unsigned long bytes) { assert(start == init_area && bytes == sizeof(init_area)); poisoned++; }
static void free_initmem_default(int value) { assert(value == -1); freed++; }
'''
    main = r'''
int main(void) {
    for (unsigned bits = 0; bits < 32; bits++) {
        board = bits & 7; integrator = bits & 8; cintegrator = bits & 16;
        fixed = poisoned = freed = retained = 0;
        free_initmem();
        assert(fixed == 1 && poisoned == 1);
        bool keep = (CONFIG_POWER_RESET_TY1208Z_MV100_RAM && board == 1) ||
                    (CONFIG_TY1208Z_ROUTER_RAM768 && board == 2) ||
                    (CONFIG_TY1208Z_ROUTER_SD_RO && board == 3);
        assert(retained == (unsigned)keep);
        assert(freed == (unsigned)(!keep && !integrator && !cintegrator));
    }
    puts("RAM768_ACTUAL_INIT_MEMORY_PASS dedicated-board retention and unchanged generic/Integrator reclamation");
}
'''
    with tempfile.TemporaryDirectory(prefix="ram768-init-") as directory:
        path = Path(directory)
        file = path / "test.c"
        file.write_text(harness + function + main)
        for selected in range(8):
            binary = path / str(selected)
            arguments = ["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                         "-fsanitize=address,undefined", "-fno-pie", "-no-pie"]
            if selected & 1:
                arguments.append("-DCONFIG_POWER_RESET_TY1208Z_MV100_RAM=1")
            if selected & 2:
                arguments.append("-DCONFIG_TY1208Z_ROUTER_RAM768=1")
            if selected & 4:
                arguments.append("-DCONFIG_TY1208Z_ROUTER_SD_RO=1")
            subprocess.run(arguments + [str(file), "-o", str(binary)], check=True)
            subprocess.run([binary], check=True)


def check_built(artifacts):
    tree = parse_fdt((artifacts / "ty1208z-diagnostic.dtb").read_bytes())
    config = (artifacts / "linux.config").read_text()
    assert ram768_profile(tree, config)
    inspection = (b"Fastboot 3.3.0-dirty (vendor)\nDDR free region baseaddr:0x1000000 size:0x3F000000\n"
                  b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\n"
                  b"loady [ off ] [ baud ]\ncrc32 address count [addr]\nbootm [addr [arg ...]]\n")
    with tempfile.TemporaryDirectory(prefix="ram768-plan-") as directory:
        path = Path(directory)
        (path / "inspection.rx").write_bytes(inspection)
        metadata = {"stop_reason": "probe-complete", "raw_file": "inspection.rx", "port": "COM9",
                    "started_utc": "2026-10-14T01:00:01+00:00",
                    "raw_sha256": hashlib.sha256(inspection).hexdigest()}
        (path / "inspection.json").write_text(json.dumps(metadata))
        boot_fixture(path / "restart.json")
        try:
            prepare(artifacts, path / "inspection.json")
            raise AssertionError("Missing fresh allocation evidence was accepted")
        except ValueError:
            pass
        plan = prepare(artifacts, path / "inspection.json", path / "restart.json")
        assert plan["memory_end"] == END and not plan["persistent_writes"]
    print("RAM768_EXACT_IMAGE_PLAN_PASS independent CRC/layout and fresh loader allocation table")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--linuxsrc", type=Path)
    args = parser.parse_args()
    actual_functions()
    if args.linuxsrc:
        actual_init_memory(args.linuxsrc)
    if args.artifacts:
        check_built(args.artifacts)
    unittest.main(argv=[__file__], verbosity=2)
