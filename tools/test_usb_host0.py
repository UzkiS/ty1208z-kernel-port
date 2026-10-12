#!/usr/bin/env python3
"""Compare actual host0 helper with pinned SDK writes/delays under sanitizers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SDK_PATH = "drivers/hisilicon/clk/hi3798mx/clk-hiusb2.c"


def oracle_source(reference):
    manifest = json.loads((ROOT / "reference/reference-manifest.json").read_text())
    entry = next(item for item in manifest["files"] if item["path"] == SDK_PATH)
    blob = (reference / SDK_PATH).read_bytes()
    if hashlib.sha256(blob).hexdigest() != entry["sha256"]:
        raise ValueError("Pinned SDK USB source identity changed")
    source = blob.decode()
    # Keep the original attribution/license, constants and function bodies in
    # the temporary oracle translation unit. Do not vendor SDK source.
    notice = source[:source.index("#include")]
    constants = "\n".join(re.findall(r"^#define .+$", source, re.MULTILINE))
    bodies = []
    for name in ("inno_phy_config_2p", "hiclk_enable_usb2_host0", "hiclk_disable_usb2_host0"):
        match = re.search(r"static (?:void|int) " + name + r"\([^\n]+\)\n\{", source)
        if not match:
            raise ValueError(f"SDK function anchor changed: {name}")
        end = match.end()
        depth = 1
        while depth and end < len(source):
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        if depth:
            raise ValueError("Unbalanced SDK function")
        bodies.append(source[match.start():end])
    return notice + constants + "\n" + "\n".join(bodies) + "\n"


HARNESS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define __iomem
#define BIT(x) (1U << (x))
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define PERI_CRG46_USB2CTRL 0xb8
#define PERI_CRG47_USB2PHY 0xbc
static u32 crg[128], peri[128], sysid;
static void *controls[5] = {&crg[0xb8 / 4], &crg[0xbc / 4],
                           &peri[0x120 / 4], &peri[0x124 / 4], &sysid};
struct event { unsigned int kind, target; u32 value; };
static struct event events[128];
static unsigned int count;
static int stuck_target = -1;
static u32 stuck_mask;
static u32 stuck_clear;
static unsigned int target(void *address)
{
    for (unsigned int i = 0; i < ARRAY_SIZE(controls); i++)
        if (address == controls[i]) return i;
    assert(!"MMIO outside five exact host0 controls");
    return 0;
}
static u32 readl(void *address)
{
    unsigned int index = target(address);
    u32 value = *(u32 *)address;
    return index == (unsigned int)stuck_target ? (value | stuck_mask) & ~stuck_clear : value;
}
static void writel(u32 value, void *address)
{
    unsigned int index = target(address);
    assert(index < 4 && count < ARRAY_SIZE(events));
    events[count++] = (struct event){1, index, value};
    *(u32 *)address = value;
}
static void udelay(unsigned int duration)
{
    assert(duration > 0 && duration <= 2000 && count < ARRAY_SIZE(events));
    events[count++] = (struct event){2, 0, duration};
}
#define mdelay(duration) udelay((duration) * 1000)
struct clk_hw { int unused; };
struct hiclk_hw { void *peri_crg_base, *peri_ctrl_base; };
static struct hiclk_hw sdk_clock = {.peri_crg_base = crg, .peri_ctrl_base = peri};
#define to_hiclk_hw(hw) ((void)(hw), &sdk_clock)
struct atomic_counter { int counter; };
static struct atomic_counter dev_open_cnt0;
static int atomic_add_return(int value, struct atomic_counter *counter)
{
    return counter->counter += value;
}
static int atomic_sub_return(int value, struct atomic_counter *counter)
{
    return counter->counter -= value;
}
static u64 get_chipid(u64 unused) { (void)unused; return sysid; }
#include "oracle.c"
#include "ty1208z-usb-host0.h"
static void initialize(u32 seed, u32 revision)
{
    for (unsigned int i = 0; i < 4; i++) {
        seed = seed * 1664525U + 1013904223U;
        *(u32 *)controls[i] = seed;
    }
    sysid = revision;
    count = 0;
    stuck_target = -1;
    stuck_mask = stuck_clear = 0;
    dev_open_cnt0.counter = 0;
}
int main(void)
{
    struct event expected[128];
    u32 final[4];
    struct clk_hw hw = {0};
    for (unsigned int revision = 0; revision < 256; revision++) {
        for (unsigned int seed = 0; seed < 8; seed++) {
            u32 id = 0x37980000U | revision;
            initialize(seed, id);
            assert(hiclk_enable_usb2_host0(&hw) == 0);
            hiclk_disable_usb2_host0(&hw);
            unsigned int expected_count = count;
            memcpy(expected, events, count * sizeof(events[0]));
            for (unsigned int i = 0; i < 4; i++) final[i] = *(u32 *)controls[i];
            initialize(seed, id);
            assert(ty1208z_usb_host0_start(controls) == 0);
            assert(ty1208z_usb_host0_stop(controls) == 0);
            assert(count == expected_count);
            for (unsigned int i = 0; i < count; i++) {
                assert(events[i].kind == expected[i].kind);
                assert(events[i].target == expected[i].target);
                assert(events[i].value == expected[i].value);
            }
            for (unsigned int i = 0; i < 4; i++) assert(*(u32 *)controls[i] == final[i]);
        }
    }
    /* Invalid MMIO/revision must never start the sequence. */
    for (unsigned int invalid = 0; invalid < 2; invalid++) {
        initialize(17, invalid ? ~0U : 0);
        assert(ty1208z_usb_host0_start(controls) == -ENODEV);
        assert(count == 0);
    }
    /* A stuck reset/interface bit prevents an HCD from starting DMA and
     * executes the real last-user shutdown before returning an error.
     */
    const u32 masks[] = {TY_USB_CONTROLLER_RESETS, TY_USB_PHY_RESETS, 0x201U};
    for (unsigned int index = 0; index < ARRAY_SIZE(masks); index++) {
        for (unsigned int bit = 0; bit < 32; bit++) {
            if (!(masks[index] & BIT(bit))) continue;
            initialize(19, 0x37980110);
            stuck_target = index;
            stuck_mask = BIT(bit);
            assert(ty1208z_usb_host0_start(controls) == -EIO);
            assert((*(u32 *)controls[0] & 0x71U) == 0);
            assert((*(u32 *)controls[1] & TY_USB_PHY_RESETS) == TY_USB_PHY_RESETS);
            assert(events[count - 1].kind == 2 && events[count - 1].value == 200);
        }
    }
    const u32 required[] = {TY_USB_CONTROLLER_CLOCKS, 3U, 8U};
    for (unsigned int index = 0; index < ARRAY_SIZE(required); index++) {
        for (unsigned int bit = 0; bit < 32; bit++) {
            if (!(required[index] & BIT(bit))) continue;
            initialize(23, 0x37980100);
            stuck_target = index;
            stuck_clear = BIT(bit);
            assert(ty1208z_usb_host0_start(controls) == -EIO);
            assert((*(u32 *)controls[0] & 0x71U) == 0);
            assert((*(u32 *)controls[1] & TY_USB_PHY_RESETS) == TY_USB_PHY_RESETS);
        }
    }
    for (unsigned int fault = 0; fault < 2; fault++) {
        initialize(29, 0x37980110);
        assert(ty1208z_usb_host0_start(controls) == 0);
        stuck_target = fault;
        stuck_mask = fault ? 0 : 1U;
        stuck_clear = fault ? 0x100U : 0;
        assert(ty1208z_usb_host0_stop(controls) == -EIO);
    }
    puts("USB_HOST0_SEQUENCE_PASS: 2048 SDK traces, revision/stuck-bit failures, shutdown readback");
    return 0;
}
"""


def execute_helper(reference):
    original = oracle_source(reference)
    with tempfile.TemporaryDirectory(prefix="usb-host0-") as directory:
        path = Path(directory)
        (path / "linux").mkdir()
        for name in ("delay.h", "errno.h", "io.h", "kernel.h", "types.h"):
            (path / "linux" / name).write_text("/* Supplied by harness. */\n")
        (path / "linux/errno.h").write_text("#include <asm-generic/errno.h>\n")
        (path / "oracle.c").write_text(original)
        (path / "test.c").write_text(HARNESS)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I", str(path),
                        "-I", str(ROOT / "overlay/drivers/clk/hisilicon"),
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=ROOT / "reference/sdk")
    args = parser.parse_args()
    execute_helper(args.reference)
