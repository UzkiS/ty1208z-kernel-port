#!/usr/bin/env python3
"""Execute actual guarded USB experiment and reject compiled-profile mutations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from inspect_images import parse_fdt
from usb_audit_profile import RESOURCES
from usb_clock_audit_profile import BASE_PATHS, NODE, usb_clock_audit_profile
from prepare_ram_boot import prepare

ROOT = Path(__file__).resolve().parents[1]
PROBE_HARNESS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint64_t resource_size_t;
#define __iomem
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define ENODEV 19
#define EINVAL 22
#define EIO 5
#define IORESOURCE_MEM 1
#define IS_ERR(p) ((p) == (void *)(intptr_t)-EIO)
#define PTR_ERR(p) (-EIO)
#define dev_info(...) ((void)0)
#define dev_warn(...) ((void)0)
struct device { int unused; };
struct platform_device { struct device dev; };
struct resource { resource_size_t start, end; };
struct snapshot { unsigned crg46, crg47, usb0, usb1, sysid0;
                  unsigned ehci_capbase, ehci_hcsparams, ehci_hccparams, ohci_revision;
                  bool controller_read; };
struct ty1208z_usb_clock_result { struct snapshot before, enabled, stopped; bool changed; int stop_error; };
static struct resource resources[8];
static bool board, extra;
static unsigned maps, calls;
static int missing_resource, map_failure, experiment_error;
static bool of_machine_is_compatible(const char *name)
{ assert(!strcmp(name, "tianyi,ty1208z-ca-usb-clock-audit")); return board; }
static struct resource *platform_get_resource(struct platform_device *p, int type, unsigned i)
{
    assert(p && type == IORESOURCE_MEM && i <= 7);
    if ((int)i == missing_resource) return NULL;
    return i < 7 || extra ? &resources[i] : NULL;
}
static resource_size_t resource_size(struct resource *r) { return r->end - r->start + 1; }
static void *devm_platform_ioremap_resource(struct platform_device *p, unsigned i)
{ assert(p && i < 7 && i == maps++); return (int)i == map_failure ? (void *)(intptr_t)-EIO : &resources[i]; }
static int ty1208z_usb_clock_audit(void *mapped[5], void *ehci, void *ohci,
                                 struct ty1208z_usb_clock_result *result)
{
    assert(maps == 7); calls++;
    for (unsigned i = 0; i < 5; i++) assert(mapped[i] == &resources[i]);
    assert(ehci == &resources[5] && ohci == &resources[6]);
    memset(result, 0, sizeof(*result)); return experiment_error;
}
"""
PROBE_MAIN = r"""
static void initialize(void)
{
    const resource_size_t addresses[] = {0xf8a220b8, 0xf8a220bc, 0xf8a20120,
        0xf8a20124, 0xf8000ee0, 0xf9890000, 0xf9880000};
    for (unsigned i = 0; i < 7; i++) {
        resources[i].start = addresses[i]; resources[i].end = addresses[i] + (i < 5 ? 4 : 0x10000) - 1;
    }
    board = true; extra = false; maps = calls = 0;
    missing_resource = map_failure = -1; experiment_error = 0;
}
int main(void)
{
    struct platform_device device = {0};
    initialize(); board = false;
    assert(hi3798mv100_usb_clock_audit_probe(&device) == -ENODEV && !maps && !calls);
    for (unsigned i = 0; i < 7; i++) {
        initialize(); missing_resource = i;
        assert(hi3798mv100_usb_clock_audit_probe(&device) == -EINVAL && !maps && !calls);
    }
    for (unsigned i = 0; i < 7; i++) for (unsigned field = 0; field < 2; field++) {
        initialize(); if (field) resources[i].end++; else resources[i].start++;
        assert(hi3798mv100_usb_clock_audit_probe(&device) == -EINVAL && !maps && !calls);
    }
    initialize(); extra = true;
    assert(hi3798mv100_usb_clock_audit_probe(&device) == -EINVAL && !maps && !calls);
    for (unsigned i = 0; i < 7; i++) {
        initialize(); map_failure = i;
        assert(hi3798mv100_usb_clock_audit_probe(&device) == -EIO && maps == i + 1 && !calls);
    }
    initialize(); experiment_error = -EIO;
    assert(hi3798mv100_usb_clock_audit_probe(&device) == -EIO && maps == 7 && calls == 1);
    initialize();
    assert(hi3798mv100_usb_clock_audit_probe(&device) == 0 && maps == 7 && calls == 1);
    puts("USB_CLOCK_AUDIT_PROBE_PASS: actual board/resources/mapping gates and failure propagation");
}
"""
HARNESS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#define EIO 5
#define ENODEV 19
typedef uint32_t u32;
#define __iomem
#define BIT(x) (1U << (x))
#define GENMASK(h, l) (((~0U) >> (31 - (h))) & ((~0U) << (l)))
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
static u32 values[5], ehci[3], ohci;
static void *controls[5];
static unsigned int writes, cap_reads, delay, fault;
static u32 readl(void *address)
{
    for (unsigned int i = 0; i < 5; i++)
        if (address == &values[i]) return values[i];
    assert(writes && (values[0] & 0x3707f) == 0x7f);
    assert((values[1] & 0xf03) == 3 && (values[2] & 0x209) == 8);
    assert(cap_reads < 4);
    assert(address == (cap_reads < 3 ? &ehci[cap_reads] : &ohci));
    cap_reads++;
    return *(u32 *)address;
}
static void writel(u32 value, void *address)
{
    unsigned int i;
    for (i = 0; i < 4; i++) if (address == &values[i]) break;
    assert(i < 4); /* No SYSID, controller operational or endpoint writes. */
    writes++;
    if (fault == 1 && i == 0 && !(value & 0x37000) && (value & 0x7f) == 0x7f)
        value |= BIT(12);
    if (fault == 2 && i == 1 && !(value & 0xf00)) value |= BIT(8);
    if (fault == 3 && i == 0 && !(value & 0x71)) value |= 0x71;
    if (fault == 4 && i == 1 && cap_reads && (value & 0xf00) == 0xf00)
        value &= ~BIT(8);
    values[i] = value;
}
static void udelay(unsigned int us)
{
    assert(us <= 2000);
    delay += us;
    assert(delay <= 20000);
}
#include "ty1208z-usb-clock-audit.h"
static void initialize(void)
{
    const u32 initial[] = {0x0013707f, 0xb01, 0xc71a8, 0, 0x37980100};
    for (unsigned int i = 0; i < 5; i++) { values[i] = initial[i]; controls[i] = &values[i]; }
    ehci[0] = 0x01000010; ehci[1] = 0x12; ehci[2] = 0x80; ohci = 0x10;
    writes = cap_reads = delay = fault = 0;
}
static void stopped(void)
{
    assert(values[0] == 0x0010000e && values[1] == 0xf03);
    assert(values[2] == 0xc71a8 && values[3] == 0xa801 && values[4] == 0x37980100);
}
int main(void)
{
    for (unsigned int field = 0; field < 5; field++) for (unsigned int bit = 0; bit < 32; bit++) {
        struct ty1208z_usb_clock_result result;
        initialize(); values[field] ^= BIT(bit);
        u32 initial[5]; for (unsigned int i = 0; i < 5; i++) initial[i] = values[i];
        assert(ty1208z_usb_clock_audit(controls, ehci, &ohci, &result) == -ENODEV);
        assert(!result.changed && !writes && !cap_reads && !delay);
        for (unsigned int i = 0; i < 5; i++) assert(values[i] == initial[i]);
    }
    struct ty1208z_usb_clock_result result;
    initialize(); values[0] = 0x7f; values[1] = 3; values[2] = 8;
    assert(ty1208z_usb_clock_audit(controls, ehci, &ohci, &result) == -ENODEV);
    assert(!writes && !cap_reads); /* Foreign active state must not touch controller. */
    for (unsigned int version = 0x10; version <= 0x11; version++) {
        initialize(); ohci = version;
        assert(ty1208z_usb_clock_audit(controls, ehci, &ohci, &result) == 0);
        assert(result.changed && result.enabled.controller_read && cap_reads == 4);
        assert(result.enabled.ehci_capbase == ehci[0] && result.enabled.ohci_revision == version);
        assert(!result.stopped.controller_read && result.stop_error == 0);
        stopped();
    }
    const u32 bad_capbase[] = {0, ~0U, 0x0100000c, 0x01000011, 0x01000084, 0x01100010};
    for (unsigned int i = 0; i < ARRAY_SIZE(bad_capbase); i++) {
        initialize(); ehci[0] = bad_capbase[i];
        assert(ty1208z_usb_clock_audit(controls, ehci, &ohci, &result) == -EIO);
        assert(cap_reads == 4 && !result.stop_error); stopped();
    }
    for (unsigned int mode = 0; mode < 5; mode++) {
        initialize();
        if (mode == 0) ehci[1] = 0;
        if (mode == 1) ehci[1] = ~0U;
        if (mode == 2) ehci[2] = ~0U;
        if (mode == 3) ohci = ~0U;
        if (mode == 4) ohci = 0;
        assert(ty1208z_usb_clock_audit(controls, ehci, &ohci, &result) == -EIO);
        assert(cap_reads == 4 && !result.stop_error); stopped();
    }
    for (unsigned int mode = 1; mode <= 4; mode++) {
        initialize(); fault = mode;
        assert(ty1208z_usb_clock_audit(controls, ehci, &ohci, &result) == -EIO);
        assert(result.changed);
        if (mode <= 2) { assert(!cap_reads && !result.stop_error); }
        else { assert(cap_reads == 4 && result.stop_error == -EIO); }
    }
    puts("USB_CLOCK_AUDIT_HELPER_PASS: actual preconditions, fixed MMIO, capabilities, bounded delays, shutdown/failure checks");
}
"""


def execute_helper():
    with tempfile.TemporaryDirectory(prefix="usb-clock-audit-") as directory:
        path = Path(directory)
        (path / "linux").mkdir()
        for name in ("bitops.h", "io.h", "types.h", "delay.h", "errno.h", "kernel.h"):
            (path / "linux" / name).write_text("/* Types and MMIO supplied by harness. */\n")
        (path / "test.c").write_text(HARNESS)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I", str(path),
                        "-I", str(ROOT / "overlay/drivers/soc/hisilicon"),
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True, timeout=10)


def execute_probe():
    source = (ROOT / "overlay/drivers/soc/hisilicon/hi3798mv100-usb-clock-audit.c").read_text()
    start = source.index("static int hi3798mv100_usb_clock_audit_probe(")
    function = source[start:source.index("static const struct of_device_id", start)]
    with tempfile.TemporaryDirectory(prefix="usb-clock-probe-") as directory:
        path = Path(directory)
        (path / "test.c").write_text(PROBE_HARNESS + function + PROBE_MAIN)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-variable", "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True, timeout=10)


def check_built(artifacts):
    tree = parse_fdt((artifacts / "ty1208z-diagnostic.dtb").read_bytes())
    if not usb_clock_audit_profile(tree, (artifacts / "linux.config").read_text()):
        raise ValueError("Compiled USB clock experiment profile is absent")
    inspection = (b"Fastboot 3.3.0-dirty (vendor)\n"
                  b"DDR free region baseaddr:0x1000000 size:0x3F000000\n"
                  b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\n"
                  b"loady [ off ] [ baud ]\ncrc32 address count [addr]\n"
                  b"bootm [addr [arg ...]]\n")
    with tempfile.TemporaryDirectory(prefix="usb-clock-plan-") as directory:
        path = Path(directory)
        (path / "inspection.rx").write_bytes(inspection)
        record = path / "inspection.json"
        record.write_text(json.dumps({"stop_reason": "probe-complete", "raw_file": "inspection.rx",
                                      "raw_sha256": hashlib.sha256(inspection).hexdigest()}))
        plan = prepare(artifacts, record)
    assert not plan["persistent_writes"] and "additional_loads" not in plan
    assert plan["header_address"] == 0x01ffffc0 and plan["load_address"] == 0x02000000
    print("USB_CLOCK_AUDIT_RAM_PLAN_PASS: actual CRC/layout/profile and bounded single-payload plan")


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tree = {"nodes": [{"path": path, "properties": {}} for path in sorted(BASE_PATHS | {NODE})]}
        self.props = {node["path"]: node["properties"] for node in self.tree["nodes"]}
        self.props["/"]["compatible"] = {"strings": ["tianyi,ty1208z-ca-usb-clock-audit", "hi3798mv100-series"]}
        self.props[NODE].update({"compatible": {"strings": ["tianyi,ty1208z-usb-clock-capability-audit"]},
                                 "reg": {"cells": RESOURCES.copy()}})
        self.config = 'CONFIG_LOCALVERSION="-ty1208z-usb-clock-audit1"\nCONFIG_HI3798MV100_USB_CLOCK_AUDIT=y\n'

    def test_exact_profile(self):
        self.assertTrue(usb_clock_audit_profile(self.tree, self.config))

    def test_resources_properties_identity_and_subsystems(self):
        for index in range(len(RESOURCES)):
            tree = copy.deepcopy(self.tree)
            props = next(n["properties"] for n in tree["nodes"] if n["path"] == NODE)
            props["reg"]["cells"][index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                usb_clock_audit_profile(tree, self.config)
        for option in ("USB_SUPPORT", "NET", "BLOCK", "MMC", "MODULES", "SMP", "DEBUG_FS",
                       "HI3798MV100_USB_AUDIT", "TY1208Z_USB_HOST0_EXPERIMENT"):
            for state in ("y", "m"):
                with self.subTest(option=option, state=state), self.assertRaises(ValueError):
                    usb_clock_audit_profile(self.tree, self.config + f"CONFIG_{option}={state}\n")
        for prop in ("clocks", "interrupts", "resets"):
            self.props[NODE][prop] = {"cells": [1]}
            with self.assertRaises(ValueError):
                usb_clock_audit_profile(self.tree, self.config)
            del self.props[NODE][prop]
        with self.assertRaises(ValueError):
            usb_clock_audit_profile(self.tree, self.config.replace("CONFIG_HI3798MV100_USB_CLOCK_AUDIT=y\n", ""))
        with self.assertRaises(ValueError):
            usb_clock_audit_profile(self.tree, self.config.replace("usb-clock-audit1", "diag1"))
        self.props["/"]["compatible"]["strings"][0] = "other,board"
        with self.assertRaises(ValueError):
            usb_clock_audit_profile(self.tree, self.config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    execute_helper()
    execute_probe()
    if args.artifacts:
        check_built(args.artifacts)
    unittest.main(argv=[__file__], verbosity=2)
