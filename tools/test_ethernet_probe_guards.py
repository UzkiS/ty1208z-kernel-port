#!/usr/bin/env python3
"""Execute actual Ethernet probes, including the opt-in higher-memory identity."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from femac_patch import HELPERS

ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t resource_size_t;
#define __iomem
#ifndef CONFIG_TY1208Z_ROUTER_RAM768
#define CONFIG_TY1208Z_ROUTER_RAM768 0
#endif
#ifndef CONFIG_TY1208Z_ROUTER_SD_RO
#define CONFIG_TY1208Z_ROUTER_SD_RO 0
#endif
#define IS_ENABLED(x) (x)
#define ARRAY_SIZE(values) (sizeof(values) / sizeof((values)[0]))
#define IORESOURCE_MEM 1
#define GFP_KERNEL 0
#define IS_ERR(value) (false)
#define PTR_ERR(value) (-EIO)
#define PHY_RESET_DELAYS_PROPERTY "hisilicon,phy-reset-delays-us"
#define MII_PHYSID1 2
#define MII_PHYSID2 3
struct device_node { bool reset, delays; };
struct device { struct device_node *of_node; };
struct resource { resource_size_t start, size; };
struct platform_device { struct device dev; struct resource resources[6]; unsigned count; };
struct phy_device { struct { int addr; } mdio; u32 phy_id; };
struct clk_init_data { const char *name; const void *ops; };
struct clk_hw { const struct clk_init_data *init; };
static const int ty1208z_ethernet_clock_ops;
static const char *board;
static unsigned resource_queries, mappings, registrations, providers, phy_reads;
static int phy_high, phy_low;
static void *allocation;
static bool of_machine_is_compatible(const char *name) { return !strcmp(board, name); }
static struct resource *platform_get_resource(struct platform_device *dev, int type, unsigned index) {
    assert(type == IORESOURCE_MEM); resource_queries++;
    return index < dev->count ? &dev->resources[index] : NULL;
}
static resource_size_t resource_size(struct resource *res) { return res->size; }
static bool of_property_read_bool(struct device_node *node, const char *name) {
    if (!strcmp(name, "resets")) return node->reset;
    assert(!strcmp(name, PHY_RESET_DELAYS_PROPERTY)); return node->delays;
}
static void *devm_kzalloc(struct device *dev, size_t size, int flags) {
    (void)dev; (void)flags; assert(!allocation); allocation = calloc(1, size);
    assert(allocation); return allocation;
}
static void *devm_platform_ioremap_resource(struct platform_device *dev, unsigned index) {
    assert(index < dev->count); mappings++; return &dev->resources[index];
}
static int devm_clk_hw_register(struct device *dev, struct clk_hw *hw) {
    (void)dev; assert(!strcmp(hw->init->name, "ty1208z-inherited-ethernet"));
    assert(hw->init->ops == &ty1208z_ethernet_clock_ops); registrations++; return 0;
}
static int of_clk_hw_simple_get;
static int devm_of_clk_add_hw_provider(struct device *dev, void *get, struct clk_hw *hw) {
    (void)dev; assert(get == &of_clk_hw_simple_get && hw); providers++; return 0;
}
#define devm_of_clk_add_hw_provider(dev, get, hw) devm_of_clk_add_hw_provider(dev, &(get), hw)
static int phy_read(struct phy_device *phy, int reg) {
    assert(phy->mdio.addr == 1); phy_reads++;
    if (reg == MII_PHYSID1) return phy_high;
    assert(reg == MII_PHYSID2); return phy_low;
}
#define phydev_info(...) ((void)0)
'''
MAIN = r'''
static struct device_node node;
static struct platform_device clockdev, macdev;
static struct phy_device phy;
static void initialize(const char *identity) {
    const resource_size_t addresses[] = {0xf8a220cc, 0xf8a22120, 0xf8a20008, 0xf8a20118, 0xf8a20844};
    free(allocation); allocation = NULL;
    resource_queries = mappings = registrations = providers = phy_reads = 0;
    board = identity; memset(&node, 0, sizeof(node));
    memset(&clockdev, 0, sizeof(clockdev)); memset(&macdev, 0, sizeof(macdev));
    clockdev.dev.of_node = macdev.dev.of_node = &node;
    clockdev.count = 5; macdev.count = 2;
    for (unsigned i = 0; i < 5; i++) clockdev.resources[i] = (struct resource){addresses[i], 4};
    macdev.resources[0] = (struct resource){0xf9840000, 0x400};
    macdev.resources[1] = (struct resource){0xf9841300, 0x200};
    phy.mdio.addr = 1; phy.phy_id = 0x20669823;
    phy_high = 0x2066; phy_low = 0x9823;
}
int main(void) {
    const char *accepted[] = {"tianyi,ty1208z-ca-diagnostic", "tianyi,ty1208z-ca-openwrt-net",
                             "tianyi,ty1208z-ca-openwrt-router-ram",
#if CONFIG_TY1208Z_ROUTER_RAM768
                             "tianyi,ty1208z-ca-openwrt-router768-ram",
#endif
#if CONFIG_TY1208Z_ROUTER_SD_RO
                             "tianyi,ty1208z-ca-openwrt-sdro-ram",
#endif
                             };
    const char *rejected[] = {"", "linux,dummy-virt", "tianyi,ty1208z-ca-openwrt-ram",
                             "tianyi,ty1208z-ca-usb-host-experiment", "tianyi,ty1208z-ca-openwrt-router",
#if !CONFIG_TY1208Z_ROUTER_RAM768
                             "tianyi,ty1208z-ca-openwrt-router768-ram",
#endif
#if !CONFIG_TY1208Z_ROUTER_SD_RO
                             "tianyi,ty1208z-ca-openwrt-sdro-ram",
#endif
                             };
    for (unsigned i = 0; i < ARRAY_SIZE(rejected); i++) {
        initialize(rejected[i]);
        assert(ty1208z_ethernet_clock_probe(&clockdev) == -ENODEV);
        assert(hisi_femac_mv100_resources(&macdev) == -ENODEV);
        assert(ty1208z_festa_probe(&phy) == -ENODEV);
        assert(!resource_queries && !mappings && !registrations && !providers && !phy_reads);
    }
    for (unsigned i = 0; i < ARRAY_SIZE(accepted); i++) {
        const char *identity = accepted[i];
        initialize(identity);
        assert(!ty1208z_ethernet_clock_probe(&clockdev));
        assert(mappings == 5 && registrations == 1 && providers == 1);
        assert(!hisi_femac_mv100_resources(&macdev));
        assert(!ty1208z_festa_probe(&phy) && phy_reads == 2);
        for (unsigned index = 0; index < 5; index++) {
            initialize(identity); clockdev.resources[index].start++;
            assert(ty1208z_ethernet_clock_probe(&clockdev) == -EINVAL && !mappings);
            initialize(identity); clockdev.resources[index].size++;
            assert(ty1208z_ethernet_clock_probe(&clockdev) == -EINVAL && !mappings);
        }
        initialize(identity); clockdev.count = 4;
        assert(ty1208z_ethernet_clock_probe(&clockdev) == -EINVAL && !mappings);
        initialize(identity); clockdev.count = 6;
        assert(ty1208z_ethernet_clock_probe(&clockdev) == -EINVAL && !mappings);
        for (unsigned index = 0; index < 2; index++) {
            initialize(identity); macdev.resources[index].start++;
            assert(hisi_femac_mv100_resources(&macdev) == -EINVAL);
            initialize(identity); macdev.resources[index].size++;
            assert(hisi_femac_mv100_resources(&macdev) == -EINVAL);
        }
        initialize(identity); macdev.count = 1;
        assert(hisi_femac_mv100_resources(&macdev) == -EINVAL);
        initialize(identity); macdev.count = 3;
        assert(hisi_femac_mv100_resources(&macdev) == -EINVAL);
        initialize(identity); node.reset = true;
        assert(hisi_femac_mv100_resources(&macdev) == -EINVAL);
        initialize(identity); node.delays = true;
        assert(hisi_femac_mv100_resources(&macdev) == -EINVAL);
        initialize(identity); phy.mdio.addr = 2;
        assert(ty1208z_festa_probe(&phy) == -ENODEV && !phy_reads);
        initialize(identity); phy.phy_id++;
        assert(ty1208z_festa_probe(&phy) == -ENODEV && !phy_reads);
        initialize(identity); phy_high = -EIO;
        assert(ty1208z_festa_probe(&phy) == -EIO && phy_reads == 1);
        initialize(identity); phy_low = -ETIMEDOUT;
        assert(ty1208z_festa_probe(&phy) == -ETIMEDOUT && phy_reads == 2);
        initialize(identity); phy_low++;
        assert(ty1208z_festa_probe(&phy) == -ENODEV && phy_reads == 2);
    }
    free(allocation);
    puts("ETHERNET_PROBE_GUARDS_PASS: actual clock/MAC/PHY probes, opt-in board, foreign/resources/ID rejection");
    return 0;
}
'''


def function(text, name):
    start = text.index("static int " + name + "(")
    opening = text.index("{", start)
    depth = 1
    for index in range(opening + 1, len(text)):
        depth += (text[index] == "{") - (text[index] == "}")
        if not depth:
            return text[start:index + 1] + "\n"
    raise ValueError("Unterminated probe function")


def run(linux=None):
    tree = linux if linux is not None else ROOT / "overlay"
    clock = (tree / "drivers/clk/hisilicon/clk-ty1208z-ethernet.c").read_text()
    phy = (tree / "drivers/net/phy/festa-ty1208z.c").read_text()
    mac = ((linux / "drivers/net/ethernet/hisilicon/hisi_femac.c").read_text()
           if linux is not None else HELPERS)
    structure = re.search(r"struct ty1208z_ethernet_clock \{[\s\S]*?\n\};", clock)[0] + "\n"
    source = PRELUDE + structure + function(clock, "ty1208z_ethernet_clock_probe")
    source += function(mac, "hisi_femac_mv100_resources") + function(phy, "ty1208z_festa_probe") + MAIN
    with tempfile.TemporaryDirectory(prefix="ethernet-probes-") as directory:
        build = Path(directory)
        (build / "test.c").write_text(source)
        binary = build / "test"
        for selected in range(4):
            arguments = ["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                         "-fsanitize=address,undefined", "-fno-pie", "-no-pie"]
            if selected & 1:
                arguments.append("-DCONFIG_TY1208Z_ROUTER_RAM768=1")
            if selected & 2:
                arguments.append("-DCONFIG_TY1208Z_ROUTER_SD_RO=1")
            subprocess.run(arguments + [str(build / "test.c"), "-o", str(binary)], check=True)
            subprocess.run([binary], check=True, timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux", type=Path)
    run(parser.parse_args().linux)
