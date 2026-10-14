#!/usr/bin/env python3
"""Execute the actual eMMC probe/shutdown with identity and MMIO traps."""
import argparse
from pathlib import Path
import subprocess
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
#define SDMMC_CLKSRC 0x0c
#define SDMMC_RINTSTS 0x44
#define SDMMC_CTRL_INT_ENABLE (1U << 4)
#define SDMMC_CTRL_DMA_ENABLE (1U << 5)
#define SDMMC_CTRL_USE_IDMAC (1U << 25)
#define STATE_IDLE 0
static bool ro_mode;
#define CONFIG_HI3798MV100_EMMC_READ_ONLY ro_mode
static bool native_mode;
#define CONFIG_TY1208Z_ROUTER_EMMC_RO native_mode
#define CONFIG_TY1208Z_OPENWRT_SYSTEM 0
static bool install_mode;
#define CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE install_mode
#define IS_ENABLED(option) (option)
struct device { void *of_node; };
struct platform_device { struct device dev; };
struct resource { uint64_t start, end; };
struct irq_data { unsigned hwirq; };
struct mmc_host { unsigned claimed; };
struct dw_mci_slot { struct mmc_host *mmc; };
struct dw_mci {
    u32 regs[64];
    struct dw_mci_slot *slot;
    int state;
    void *mrq, *cmd, *data;
};
static struct dw_mci host;
static struct mmc_host mmc;
static struct dw_mci_slot slot = {&mmc};
#define mci_readl(host, reg) ((host)->regs[SDMMC_##reg / 4])
#define mci_writel(host, reg, value) ((host)->regs[SDMMC_##reg / 4] = (value))
static void mmc_claim_host(struct mmc_host *h) { assert(h == &mmc); h->claimed++; }
static int mv100_ident_data;
static struct resource resources[3];
static u32 crg, controller[1024];
static struct irq_data irq;
static bool board, extra;
static const char *board_name;
static int missing, map_failure, irq_error;
static const char *property;
static unsigned maps, reads, registered, removed, completion, errors;
static bool of_machine_is_compatible(const char *name)
{ return board && !strcmp(name, board_name); }
static struct resource *platform_get_resource(struct platform_device *p, int type, unsigned i)
{ assert(p && type == IORESOURCE_MEM && i < 3); return (int)i == missing || (i == 2 && !extra) ? NULL : &resources[i]; }
static uint64_t resource_size(struct resource *r) { return r->end - r->start + 1; }
static int platform_get_irq(struct platform_device *p, unsigned i) { assert(p && !i); return irq_error ? irq_error : 17; }
static struct irq_data *irq_get_irq_data(int n) { assert(n == 17); return &irq; }
static void *of_find_property(void *node, const char *name, void *len)
{ assert(node && name && !len); return property && !strcmp(property, name) ? &irq : NULL; }
static void *devm_platform_ioremap_resource(struct platform_device *p, unsigned i)
{ assert(p && i == 1 && maps++ == 0); return map_failure == 1 ? (void *)(intptr_t)-EIO : &crg; }
static void *devm_ioremap(struct device *d, uint64_t start, uint64_t size)
{ assert(d && start == 0xf9830000 && size == 0x1000 && maps++ == 1); return map_failure == 0 ? NULL : controller; }
static void devm_iounmap(struct device *d, void *mapping) { assert(d && mapping == controller); }
static u32 readl(void *address)
{
    void *sequence[] = {&crg, (void *)controller + 0x6c, (void *)controller + 0x70};
    assert(reads < 3 && address == sequence[reads++]); return *(u32 *)address;
}
static int dev_err_probe(struct device *d, int code, const char *format, u32 value)
{ assert(d && format); (void)value; return code; }
static void dev_info(struct device *d, const char *format, ...)
{ assert(d && format); completion++; }
static void dev_err(struct device *d, const char *format) { assert(d && format); errors++; }
static int dw_mci_pltfm_register(struct platform_device *p, void *data)
{ assert(p && data == &mv100_ident_data && maps == 2 && reads == 3); registered++; return 0; }
static void dw_mci_pltfm_remove(struct platform_device *p) { assert(p); removed++; }
static struct dw_mci *platform_get_drvdata(struct platform_device *p) { assert(p); return &host; }
static void initialize(void)
{
    resources[0] = (struct resource){0xf9830000, 0xf9830fff};
    resources[1] = (struct resource){0xf8a220a0, 0xf8a220a3};
    crg = 0x40103; irq.hwirq = 67;
    controller[SDMMC_VERID / 4] = 0x5342270a; controller[SDMMC_HCON / 4] = 0x00e44c81;
    board = true; extra = false; missing = map_failure = -1; irq_error = 0; property = NULL;
    board_name = "tianyi,ty1208z-ca-emmc-ro-ram";
    maps = reads = registered = removed = completion = errors = 0;
}
/* ACTUAL */
int main(void)
{
    struct platform_device p = {.dev.of_node = &p};
    const char *identities[] = {"tianyi,ty1208z-ca-emmc-ro-ram", "tianyi,ty1208z-ca-openwrt-emmcro-ram", "foreign"};
    ro_mode = true;
    for (unsigned selected = 0; selected < 2; selected++) {
        native_mode = selected;
        for (unsigned i = 0; i < 3; i++) {
            initialize(); board_name = identities[i];
            bool accepted = i == 0 || (i == 1 && selected);
            assert(mv100_ident_probe(&p) == (accepted ? 0 : -ENODEV));
            assert(registered == (unsigned)accepted);
            if (!accepted) assert(!maps && !reads);
        }
    }
    native_mode = false;
    ro_mode = true; initialize(); board = false;
    assert(mv100_ident_probe(&p) == -ENODEV && !maps && !reads && !registered);
    ro_mode = false; assert(mv100_ident_probe(&p) == 0 && registered == 1);
    ro_mode = true;
    for (int i = 0; i < 2; i++) {
        initialize(); missing = i;
        assert(mv100_ident_probe(&p) == -EINVAL && !maps && !registered);
        initialize(); resources[i].start++; assert(mv100_ident_probe(&p) == -EINVAL && !maps);
        initialize(); resources[i].end++; assert(mv100_ident_probe(&p) == -EINVAL && !maps);
        initialize(); map_failure = i;
        assert(mv100_ident_probe(&p) == (i ? -EIO : -ENOMEM) && !registered);
    }
    initialize(); extra = true; assert(mv100_ident_probe(&p) == -EINVAL && !maps);
    initialize(); irq.hwirq = 66; assert(mv100_ident_probe(&p) == -EINVAL && !maps);
    initialize(); irq_error = -EIO; assert(mv100_ident_probe(&p) == -EIO && !maps);
    const char *properties[] = {"clocks", "resets", "mmc-pwrseq", "vmmc-supply", "vqmmc-supply"};
    for (unsigned i = 0; i < 5; i++) {
        initialize(); property = properties[i]; assert(mv100_ident_probe(&p) == -EINVAL && !maps);
    }
    for (unsigned bit = 0; bit < 32; bit++) {
        initialize(); crg ^= 1U << bit;
        assert(mv100_ident_probe(&p) == -ENODEV && maps == 1 && reads == 1 && !registered);
        initialize(); controller[SDMMC_VERID / 4] ^= 1U << bit;
        assert(mv100_ident_probe(&p) == -ENODEV && !registered);
        initialize(); controller[SDMMC_HCON / 4] ^= 1U << bit;
        assert(mv100_ident_probe(&p) == -ENODEV && !registered);
    }
    initialize(); assert(!mv100_ident_probe(&p) && registered == 1);
    ro_mode = false; mv100_ident_shutdown(&p); assert(!removed && !completion && !errors);
    ro_mode = true; mv100_ident_shutdown(&p); assert(removed == 1 && completion == 1 && !errors);
    const unsigned offsets[] = {SDMMC_INTMASK, SDMMC_CLKENA, SDMMC_IDINTEN, SDMMC_CTRL};
    for (unsigned i = 0; i < 4; i++) {
        host.regs[offsets[i] / 4] = i == 3 ? SDMMC_CTRL_DMA_ENABLE : 1;
        mv100_ident_shutdown(&p); assert(errors == i + 1 && completion == 1);
        host.regs[offsets[i] / 4] = 0;
    }
    puts("EMMC_RO_PROBE_SHUTDOWN_PASS: actual identity/resource/IRQ/provider/map guards and conditional host removal/readback; no hardware access");
    install_mode = true;
    memset(&host, 0, sizeof(host));
    host.slot = &slot;
    host.regs[SDMMC_INTMASK / 4] = 0xffffffff;
    host.regs[SDMMC_CLKENA / 4] = 1;
    host.regs[SDMMC_CLKSRC / 4] = 1;
    host.regs[SDMMC_IDINTEN / 4] = 0xffffffff;
    host.regs[SDMMC_CTRL / 4] = SDMMC_CTRL_INT_ENABLE | SDMMC_CTRL_DMA_ENABLE | SDMMC_CTRL_USE_IDMAC;
    unsigned prior_removed = removed, prior_completion = completion;
    mv100_ident_shutdown(&p);
    assert(mmc.claimed == 1 && removed == prior_removed && completion == prior_completion + 1);
    assert(!mci_readl(&host, INTMASK) && !mci_readl(&host, CLKENA) && !mci_readl(&host, CLKSRC));
    assert(!mci_readl(&host, IDINTEN) && !mci_readl(&host, CTRL));
    assert(mci_readl(&host, RINTSTS) == 0xffffffff);
    for (unsigned active = 0; active < 4; active++) {
        host.state = active == 0;
        host.mrq = active == 1 ? &p : NULL;
        host.cmd = active == 2 ? &p : NULL;
        host.data = active == 3 ? &p : NULL;
        host.regs[SDMMC_CLKENA / 4] = 1;
        unsigned prior_errors = errors;
        mv100_ident_shutdown(&p);
        assert(errors == prior_errors + 1 && removed == prior_removed);
        assert(completion == prior_completion + 1 && mci_readl(&host, CLKENA) == 1);
    }
    host.slot = NULL;
    unsigned prior_claimed = mmc.claimed;
    mv100_ident_shutdown(&p);
    assert(mmc.claimed == prior_claimed && removed == prior_removed);
    puts("EMMC_PERSISTENT_SHUTDOWN_PASS: actual idle host retained and IRQ/PIO clock quiesced; active/missing hosts do not write MMIO");
}
'''


def test(linuxsrc):
    relative = 'drivers/mmc/host/dw_mmc-hi3798mv100-ident.c'
    source = (linuxsrc / relative).read_text()
    assert source == (ROOT / 'overlay' / relative).read_text()
    function = source[source.index('static int mv100_ident_probe('):source.index('static const struct of_device_id')]
    core = (linuxsrc / 'drivers/mmc/host/dw_mmc.c').read_text()
    remove = core[core.index('void dw_mci_remove('):core.index('EXPORT_SYMBOL(dw_mci_remove)')]
    assert remove.index('dw_mci_cleanup_slot') < remove.index('mci_writel(host, INTMASK, 0)') < remove.index('mci_writel(host, CLKENA, 0)')
    with tempfile.TemporaryDirectory(prefix='emmc-ro-driver-') as directory:
        path = Path(directory)
        (path / 'test.c').write_text(HARNESS.replace('/* ACTUAL */', function))
        binary = path / 'test'
        subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie', str(path / 'test.c'),
                        '-o', str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linuxsrc', type=Path, required=True)
    test(parser.parse_args().linuxsrc)
