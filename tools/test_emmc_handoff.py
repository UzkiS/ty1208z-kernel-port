#!/usr/bin/env python3
"""Execute the actual restricted PIO takeover against inherited DMA/IRQ state."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--linuxsrc", type=Path, required=True)
args = parser.parse_args()
header = (args.linuxsrc / "drivers/mmc/host/dw_mmc.h").read_text()
driver = (ROOT / "overlay/drivers/mmc/host/dw_mmc-hi3798mv100-ident.c").read_text()
init = "static int mv100_ident_init(" + driver.split(
    "static int mv100_ident_init(", 1)[1].split("\nstatic int mv100_ident_slot", 1)[0]
names = set(re.findall(r"\bSDMMC_[A-Z0-9_]+\b", init))
names.update("SDMMC_" + reg for reg in re.findall(r"mci_(?:readl|writel)\(host, ([A-Z0-9_]+)", init))
defines = []
for name in sorted(names):
    match = re.search(r"^#define " + name + r"\s+[^\n]+$", header, re.M)
    if not match or match[0].endswith("\\"):
        raise ValueError(f"Expected simple fixed register definition: {name}")
    defines.append(match[0])
harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#define BIT(n) (1U << (n))
/* DEFINES */
struct pdata { unsigned int fifo_depth; };
struct dw_mci { unsigned int bus_hz; struct pdata *pdata; uint32_t regs[64]; };
static unsigned int writes;
#define dev_info(...) ((void)0)
#define mci_readl(host, reg) ((host)->regs[SDMMC_##reg / 4])
static void write_reg(struct dw_mci *host, unsigned int reg, uint32_t value) {
    assert(reg == SDMMC_INTMASK || reg == SDMMC_IDINTEN || reg == SDMMC_BMOD ||
           reg == SDMMC_CTRL || reg == SDMMC_IDSTS || reg == SDMMC_RINTSTS);
    if (reg == SDMMC_IDSTS || reg == SDMMC_RINTSTS)
        host->regs[reg / 4] &= ~value; /* actual W1C semantics */
    else
        host->regs[reg / 4] = value;
    writes++;
}
#define mci_writel(host, reg, value) write_reg(host, SDMMC_##reg, value)
/* INIT */
int main(void) {
    struct pdata pdata = { .fifo_depth = 256 };
    struct dw_mci inherited = { .bus_hz = 100000000, .pdata = &pdata };
    inherited.regs[SDMMC_VERID / 4] = 0x5342270a;
    inherited.regs[SDMMC_HCON / 4] = 0x00e44c81;
    inherited.regs[SDMMC_CTRL / 4] = 0x08000000 | SDMMC_CTRL_INT_ENABLE |
                                  SDMMC_CTRL_DMA_ENABLE | SDMMC_CTRL_USE_IDMAC;
    inherited.regs[SDMMC_BMOD / 4] = SDMMC_IDMAC_ENABLE | BIT(1);
    inherited.regs[SDMMC_INTMASK / 4] = 0xffffffff;
    inherited.regs[SDMMC_IDINTEN / 4] = 0x337;
    inherited.regs[SDMMC_IDSTS / 4] = 0x337;
    inherited.regs[SDMMC_RINTSTS / 4] = 0xffffffff;
    for (int invalid = 0; invalid < 4; invalid++) {
        struct dw_mci host = inherited;
        struct pdata changed = pdata;
        host.pdata = &changed;
        if (invalid == 0) host.bus_hz = 50000000;
        if (invalid == 1) changed.fifo_depth = 128;
        if (invalid == 2) host.regs[SDMMC_VERID / 4] ^= 1;
        if (invalid == 3) host.regs[SDMMC_HCON / 4] ^= 1;
        writes = 0;
        assert(mv100_ident_init(&host) == -ENODEV && writes == 0);
    }
    writes = 0;
    assert(mv100_ident_init(&inherited) == 0 && writes > 0);
    assert(inherited.regs[SDMMC_CTRL / 4] == 0x08000000);
    assert(inherited.regs[SDMMC_BMOD / 4] == BIT(1));
    assert(inherited.regs[SDMMC_INTMASK / 4] == 0);
    assert(inherited.regs[SDMMC_IDINTEN / 4] == 0);
    assert(inherited.regs[SDMMC_IDSTS / 4] == 0);
    assert(inherited.regs[SDMMC_RINTSTS / 4] == 0);
    puts("EMMC_HANDOFF_PASS: inherited DMA/interrupts quiesced; mismatches write nothing");
}
'''.replace("/* DEFINES */", "\n".join(defines)).replace("/* INIT */", init)
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                    str(temp / "test.c"), "-o", str(temp / "test")], check=True)
    subprocess.run([str(temp / "test")], check=True)
