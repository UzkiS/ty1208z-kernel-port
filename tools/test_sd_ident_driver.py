#!/usr/bin/env python3
"""Run actual SD probe/slot/shutdown with resource, identity and MMIO traps."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define __iomem
#define IORESOURCE_MEM 1
#define IS_ERR(x) ((intptr_t)(x) == -EIO)
#define PTR_ERR(x) (-EIO)
#define SDMMC_VERID 0x6c
#define SDMMC_HCON 0x70
#define SDMMC_INTMASK 0x24
#define SDMMC_CLKENA 0x10
#define SDMMC_IDINTEN 0x90
#define SDMMC_CTRL 0
#define SDMMC_CTRL_DMA_ENABLE (1U << 5)
#define SDMMC_CTRL_USE_IDMAC (1U << 25)
#define MMC_CAP_NEEDS_POLL 1
#define MMC_CAP2_NO_MMC 2
#define MMC_CAP2_NO_SDIO 4
static bool ro_mode, native_mode, native_identity;
#define CONFIG_HI3798MV100_SD_READ_ONLY ro_mode
#define CONFIG_TY1208Z_ROUTER_SD_RO native_mode
#define CONFIG_TY1208Z_OPENWRT_SYSTEM 0
#define IS_ENABLED(config) (config)
struct device { void *of_node; };
struct platform_device { struct device dev; };
struct resource { uint64_t start, end; };
struct irq_data { unsigned hwirq; };
struct mmc_host { unsigned caps, caps2, pm_caps, f_max, max_blk_size, max_blk_count, max_req_size, max_seg_size, dsr_req; };
struct dw_mci_slot { struct mmc_host *mmc; };
struct dw_mci { u32 regs[64]; };
static struct dw_mci host;
#define mci_readl(host, reg) ((host)->regs[SDMMC_##reg / 4])
static int mv100_sd_ident_data;
static struct resource resources[4];
static u32 crg, ldo, controller[1024];
static struct irq_data irq;
static bool board, extra;
static int missing, map_failure, irq_error;
static const char *property;
static unsigned maps, reads, registered, removed;
static unsigned completion, errors;
static bool of_machine_is_compatible(const char *name)
{
    assert(!strcmp(name, "tianyi,ty1208z-ca-sd-ro-ram") ||
           !strcmp(name, "tianyi,ty1208z-ca-sd-ident-ram") ||
           !strcmp(name, "tianyi,ty1208z-ca-openwrt-sdro-ram"));
    const char *identity = native_identity ? "tianyi,ty1208z-ca-openwrt-sdro-ram" :
                           ro_mode ? "tianyi,ty1208z-ca-sd-ro-ram" : "tianyi,ty1208z-ca-sd-ident-ram";
    return board && !strcmp(name, identity);
}
static struct resource *platform_get_resource(struct platform_device *p, int type, unsigned i)
{ assert(p && type == IORESOURCE_MEM && i < 4); return (int)i == missing || (i == 3 && !extra) ? NULL : &resources[i]; }
static uint64_t resource_size(struct resource *r) { return r->end - r->start + 1; }
static int platform_get_irq(struct platform_device *p, unsigned i) { assert(p && !i); return irq_error ? irq_error : 17; }
static struct irq_data *irq_get_irq_data(int number) { assert(number == 17); return &irq; }
static void *of_find_property(void *node, const char *name, void *len)
{ assert(node && name && !len); return property && !strcmp(property, name) ? &irq : NULL; }
static void *devm_platform_ioremap_resource(struct platform_device *p, unsigned i)
{ assert(p && (i == 1 || i == 2) && maps++ == i - 1); return (int)i == map_failure ? (void *)(intptr_t)-EIO : i == 1 ? &crg : &ldo; }
static void *devm_ioremap(struct device *d, uint64_t start, uint64_t size)
{ assert(d && start == 0xf9820000 && size == 0x1000 && maps++ == 2); return map_failure == 0 ? NULL : controller; }
static void devm_iounmap(struct device *d, void *mapping) { assert(d && mapping == controller); }
static u32 readl(void *address)
{
    void *sequence[] = {&crg, &ldo, (void *)controller + 0x6c, (void *)controller + 0x70};
    assert(reads < 4 && address == sequence[reads++]);
    return *(u32 *)address;
}
static int dev_err_probe(struct device *d, int code, const char *format, u32 value)
{ assert(d && format); (void)value; return code; }
static void dev_info(struct device *d, const char *format) { assert(d && format); completion++; }
static void dev_err(struct device *d, const char *format) { assert(d && format); errors++; }
static int dw_mci_pltfm_register(struct platform_device *p, void *data)
{ assert(p && data == &mv100_sd_ident_data && maps == 3 && reads == 4); registered++; return 0; }
static void dw_mci_pltfm_remove(struct platform_device *p) { assert(p); removed++; }
static struct dw_mci *platform_get_drvdata(struct platform_device *p) { assert(p); return &host; }
static void initialize(void)
{
    resources[0] = (struct resource){0xf9820000, 0xf9820fff};
    resources[1] = (struct resource){0xf8a2209c, 0xf8a2209f};
    resources[2] = (struct resource){0xf8a2011c, 0xf8a2011f};
    crg = 0x203; ldo = 0x60; irq.hwirq = 66;
    controller[SDMMC_VERID / 4] = 0x5342270a; controller[SDMMC_HCON / 4] = 0x00e44c81;
    board = true; extra = false; missing = map_failure = -1; irq_error = 0; property = NULL;
    maps = reads = registered = removed = 0;
}
'''
MAIN = r'''
static void exercise_profile(bool read_only, bool native)
{
    ro_mode = read_only; native_mode = native_identity = native;
    completion = errors = 0;
    struct platform_device p = {.dev.of_node = &p};
    initialize(); board = false;
    assert(mv100_sd_ident_probe(&p) == -ENODEV && !maps && !registered);
    for (int i = 0; i < 3; i++) {
        initialize(); missing = i;
        assert(mv100_sd_ident_probe(&p) == -EINVAL && !maps && !registered);
        initialize(); resources[i].start++;
        assert(mv100_sd_ident_probe(&p) == -EINVAL && !maps);
        initialize(); resources[i].end++;
        assert(mv100_sd_ident_probe(&p) == -EINVAL && !maps);
        initialize(); map_failure = i;
        assert(mv100_sd_ident_probe(&p) == (i ? -EIO : -ENOMEM) && !registered);
    }
    initialize(); extra = true;
    assert(mv100_sd_ident_probe(&p) == -EINVAL && !maps);
    initialize(); irq.hwirq = 67;
    assert(mv100_sd_ident_probe(&p) == -EINVAL && !maps);
    initialize(); irq_error = -EIO;
    assert(mv100_sd_ident_probe(&p) == -EIO && !maps);
    const char *properties[] = {"clocks", "resets", "mmc-pwrseq", "vmmc-supply", "vqmmc-supply"};
    for (unsigned i = 0; i < 5; i++) { initialize(); property = properties[i]; assert(mv100_sd_ident_probe(&p) == -EINVAL && !maps); }
    for (unsigned bit = 0; bit < 32; bit++) {
        initialize(); crg ^= 1U << bit;
        assert(mv100_sd_ident_probe(&p) == -ENODEV && maps == 1 && reads == 1 && !registered);
        initialize(); ldo ^= 1U << bit;
        assert(mv100_sd_ident_probe(&p) == -ENODEV && maps == 2 && reads == 2 && !registered);
        initialize(); controller[SDMMC_VERID / 4] ^= 1U << bit;
        assert(mv100_sd_ident_probe(&p) == -ENODEV && !registered);
        initialize(); controller[SDMMC_HCON / 4] ^= 1U << bit;
        assert(mv100_sd_ident_probe(&p) == -ENODEV && !registered);
    }
    initialize(); assert(!mv100_sd_ident_probe(&p) && registered == 1);
    struct mmc_host mmc; memset(&mmc, 0xff, sizeof(mmc));
    struct dw_mci_slot slot = {.mmc = &mmc};
    assert(!mv100_sd_ident_slot(&slot));
    assert(mmc.caps == MMC_CAP_NEEDS_POLL && mmc.caps2 == (MMC_CAP2_NO_MMC | MMC_CAP2_NO_SDIO));
    assert(!mmc.pm_caps && mmc.f_max == 25000000 && mmc.max_blk_size == 512 && mmc.max_blk_count == (ro_mode ? 8U : 1U) && mmc.max_req_size == 512 * mmc.max_blk_count && mmc.max_seg_size == mmc.max_req_size && !mmc.dsr_req);
    ro_mode = true;
    initialize();
    assert(!mv100_sd_ident_probe(&p));
    assert(!mv100_sd_ident_slot(&slot));
    assert(mmc.caps == MMC_CAP_NEEDS_POLL && mmc.caps2 == (MMC_CAP2_NO_MMC | MMC_CAP2_NO_SDIO));
    assert(mmc.max_blk_count == 8 && mmc.max_req_size == 4096 && mmc.max_seg_size == 4096 && !mmc.dsr_req);
    ro_mode = false;
    mv100_sd_ident_shutdown(&p); assert(removed == 1 && completion == 1 && !errors);
    const unsigned offsets[] = {SDMMC_INTMASK, SDMMC_CLKENA, SDMMC_IDINTEN, SDMMC_CTRL};
    for (unsigned i = 0; i < 4; i++) {
        host.regs[offsets[i] / 4] = i == 3 ? SDMMC_CTRL_DMA_ENABLE : 1;
        mv100_sd_ident_shutdown(&p); assert(errors == i + 1 && completion == 1);
        host.regs[offsets[i] / 4] = 0;
    }
    puts("SD_IDENT_PROBE_PASS: actual identity/resource/IRQ/provider/map gates, slot restrictions and DW shutdown dispatch");
}
int main(void)
{
    exercise_profile(false, false);
    exercise_profile(true, false);
    exercise_profile(true, true);
    struct platform_device p = {.dev.of_node = &p};
    ro_mode = true; native_identity = true; native_mode = false;
    initialize();
    assert(mv100_sd_ident_probe(&p) == -ENODEV && !maps && !reads && !registered);
    native_mode = true; ro_mode = false;
    initialize();
    assert(mv100_sd_ident_probe(&p) == -ENODEV && !maps && !reads && !registered);
    puts("SD_NATIVE_OPT_IN_PROBE_PASS: dedicated board requires both native and read-only selections before MMIO");
}
'''


def test(linuxsrc):
    source = (ROOT / "overlay/drivers/mmc/host/dw_mmc-hi3798mv100-sd-ident.c").read_text()
    slot = source[source.index("static int mv100_sd_ident_slot("):source.index("static int mv100_sd_ident_validate(")]
    probe = source[source.index("static int mv100_sd_ident_probe("):source.index("static const struct of_device_id")]
    with tempfile.TemporaryDirectory(prefix="sd-ident-driver-") as directory:
        path = Path(directory)
        (path / "test.c").write_text(HARNESS + slot + probe + MAIN)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/test_emmc_handoff.py"), "--linuxsrc", str(linuxsrc), "--profile", "sd"], check=True)
    core = (linuxsrc / "drivers/mmc/host/dw_mmc.c").read_text()
    remove = core[core.index("void dw_mci_remove("):core.index("EXPORT_SYMBOL(dw_mci_remove)")]
    assert remove.index("dw_mci_cleanup_slot") < remove.index("mci_writel(host, INTMASK, 0)") < remove.index("mci_writel(host, CLKENA, 0)")
    assert "reset_control_assert(host->pdata->rstc)" in remove


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linuxsrc", type=Path, required=True)
    args = parser.parse_args()
    test(args.linuxsrc)
