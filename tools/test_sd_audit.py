#!/usr/bin/env python3
"""Execute the actual SD probe with inactive-clock and resource/MMIO traps."""
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
from sd_audit_profile import sd_audit_profile, BASE_PATHS, NODE, RESOURCES

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t resource_size_t;
#define __iomem
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define ENODEV 19
#define EINVAL 22
#define EIO 5
#define IORESOURCE_MEM 1
#define IS_ERR(x) ((intptr_t)(x) == -EIO)
#define PTR_ERR(x) (-EIO)
struct device { int unused; };
struct platform_device { struct device dev; };
struct resource { resource_size_t start, end; };
static struct resource resources[4];
static u32 controller[1024], crg, ldo;
static bool board, extra;
static int missing, map_failure;
static unsigned maps, reads, controller_reads;
static bool of_machine_is_compatible(const char *name)
{ assert(!strcmp(name, "tianyi,ty1208z-ca-diagnostic")); return board; }
static struct resource *platform_get_resource(struct platform_device *p, int type, unsigned i)
{ assert(p && type == IORESOURCE_MEM && i < 4); return (int)i == missing || (i == 3 && !extra) ? NULL : &resources[i]; }
static resource_size_t resource_size(struct resource *r) { return r->end - r->start + 1; }
static void *devm_platform_ioremap_resource(struct platform_device *p, unsigned i)
{
    const unsigned order[] = {1, 2, 0};
    assert(p && maps < 3 && i == order[maps++]);
    return (int)i == map_failure ? (void *)(intptr_t)-EIO : i == 0 ? (void *)controller : i == 1 ? (void *)&crg : &ldo;
}
static u32 readl(void *address)
{
    reads++;
    if (address == &crg) { assert(reads == 1); return crg; }
    if (address == &ldo) { assert(reads == 2); return ldo; }
    const unsigned offsets[] = {8, 12, 16, 24, 76, 80, 84, 104, 108, 112};
    assert((crg & 0x13) == 3 && maps == 3 && controller_reads < 10);
    assert(address == (void *)controller + offsets[controller_reads++]);
    return *(u32 *)address;
}
static void dev_info(struct device *dev, const char *format, ...)
{ assert(dev && format); }
static void initialize(void)
{
    const resource_size_t addresses[] = {0xf9820000, 0xf8a2209c, 0xf8a2011c};
    for (unsigned i = 0; i < 3; i++) {
        resources[i].start = addresses[i]; resources[i].end = addresses[i] + (i == 0 ? 0x1000 : 4) - 1;
    }
    board = true; extra = false; missing = map_failure = -1;
    maps = reads = controller_reads = 0; crg = 0x42103; ldo = 0x60;
}
'''
MAIN = r'''
int main(void)
{
    struct platform_device dev = {0};
    initialize(); board = false;
    assert(hi3798mv100_sd_audit_probe(&dev) == -ENODEV && !maps && !reads);
    for (unsigned i = 0; i < 3; i++) {
        initialize(); missing = i;
        assert(hi3798mv100_sd_audit_probe(&dev) == -EINVAL && !maps && !reads);
        for (unsigned field = 0; field < 2; field++) {
            initialize(); if (field) resources[i].end++; else resources[i].start++;
            assert(hi3798mv100_sd_audit_probe(&dev) == -EINVAL && !maps && !reads);
        }
        initialize(); map_failure = i;
        assert(hi3798mv100_sd_audit_probe(&dev) == -EIO && !controller_reads);
    }
    initialize(); extra = true;
    assert(hi3798mv100_sd_audit_probe(&dev) == -EINVAL && !maps);
    for (unsigned low = 0; low < 32; low++) for (unsigned rate = 0; rate < 4; rate++) {
        initialize(); crg = 0x42000 | (rate << 8) | low;
        bool active = (low & 0x13) == 3;
        assert(hi3798mv100_sd_audit_probe(&dev) == 0);
        assert(maps == (active ? 3U : 2U) && reads == (active ? 12U : 2U));
        assert(controller_reads == (active ? 10U : 0U));
    }
    puts("SD_AUDIT_PROBE_PASS: actual resource/map gates, clock/reset denial, exact read-only MMIO sequence");
}
'''


def execute_probe():
    source = (ROOT / "overlay/drivers/soc/hisilicon/hi3798mv100-sd-audit.c").read_text()
    start = source.index("static int hi3798mv100_sd_audit_probe(")
    function = source[start:source.index("static const struct of_device_id", start)]
    with tempfile.TemporaryDirectory(prefix="sd-audit-") as directory:
        path = Path(directory)
        (path / "test.c").write_text(HARNESS + function + MAIN)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


class ProfileTests(unittest.TestCase):
    def test_resource_config_and_peripheral_mutations(self):
        tree = {"nodes": [{"path": path, "properties": {}} for path in sorted(BASE_PATHS | {NODE})]}
        props = {n["path"]: n["properties"] for n in tree["nodes"]}
        props["/"]["compatible"] = {"strings": ["tianyi,ty1208z-ca-diagnostic", "hi3798mv100-series"]}
        props[NODE].update({"compatible": {"strings": ["tianyi,ty1208z-sd-register-audit"]},
                            "reg": {"cells": RESOURCES.copy()}})
        config = 'CONFIG_LOCALVERSION="-ty1208z-sd-audit1"\nCONFIG_HI3798MV100_SD_AUDIT=y\n'
        self.assertTrue(sd_audit_profile(tree, config))
        for i in range(len(RESOURCES)):
            changed = copy.deepcopy(tree)
            next(n for n in changed["nodes"] if n["path"] == NODE)["properties"]["reg"]["cells"][i] ^= 1
            with self.assertRaises(ValueError):
                sd_audit_profile(changed, config)
        for option in ("MMC", "BLOCK", "NET", "DEBUG_FS", "MODULES", "SMP", "USB_SUPPORT"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                sd_audit_profile(tree, config + f"CONFIG_{option}=y\n")
        with self.assertRaises(ValueError):
            sd_audit_profile(tree, "")
        props[NODE]["clocks"] = {"cells": [1]}
        with self.assertRaises(ValueError):
            sd_audit_profile(tree, config)


def check_built(artifacts):
    tree = parse_fdt((artifacts / "ty1208z-diagnostic.dtb").read_bytes())
    assert sd_audit_profile(tree, (artifacts / "linux.config").read_text())
    inspection = (b"Fastboot 3.3.0-dirty (vendor)\n"
                  b"DDR free region baseaddr:0x1000000 size:0x3F000000\n"
                  b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\n"
                  b"loady [ off ] [ baud ]\ncrc32 address count [addr]\nbootm [addr [arg ...]]\n")
    with tempfile.TemporaryDirectory(prefix="sd-audit-plan-") as directory:
        path = Path(directory)
        (path / "inspection.rx").write_bytes(inspection)
        record = path / "inspection.json"
        record.write_text(json.dumps({"stop_reason": "probe-complete", "raw_file": "inspection.rx",
                                      "raw_sha256": hashlib.sha256(inspection).hexdigest()}))
        plan = prepare(artifacts, record)
    assert not plan["persistent_writes"] and "additional_loads" not in plan
    print("SD_AUDIT_RAM_PLAN_PASS: compiled DT/config, CRC/layout and bounded placement")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    execute_probe()
    if args.artifacts:
        check_built(args.artifacts)
    unittest.main(argv=[__file__], verbosity=2)
