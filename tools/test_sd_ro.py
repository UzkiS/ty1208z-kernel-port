#!/usr/bin/env python3
"""Run actual read-only request/queue and forced-ro callbacks under sanitizers."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from test_sd_ident import HARNESS, test as test_policy

MAIN = r'''
int main(void)
{
    struct mmc_command cmd = {0}, stop = {0}, sbc = {0};
    struct mmc_data data = {.flags = MMC_DATA_READ, .blocks = 1, .blksz = 512};
    struct mmc_request mrq = {.cmd = &cmd, .data = &data};
    cmd.data = &data;
    const unsigned read_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
    const unsigned stop_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC;
    stop.opcode = MMC_STOP_TRANSMISSION; stop.flags = stop_flags;
    cmd.flags = read_flags;
    for (unsigned opcode = 0; opcode < 64; opcode++) {
        for (unsigned blocks = 1; blocks < 11; blocks++) {
            cmd.opcode = opcode; cmd.arg = 0; data.blocks = blocks;
            mrq.stop = data.stop = blocks > 1 ? &stop : NULL;
            for (unsigned direction = 1; direction < 4; direction++) {
                data.flags = direction;
                check(&mrq, direction == MMC_DATA_READ && blocks <= 8 &&
                      opcode == (blocks == 1 ? MMC_READ_SINGLE_BLOCK : MMC_READ_MULTIPLE_BLOCK));
            }
        }
    }
    data.flags = MMC_DATA_READ;
    for (unsigned blocks = 1; blocks <= 8; blocks++) {
        data.blocks = blocks;
        cmd.opcode = blocks == 1 ? MMC_READ_SINGLE_BLOCK : MMC_READ_MULTIPLE_BLOCK;
        mrq.stop = data.stop = blocks == 1 ? NULL : &stop;
        for (unsigned position = 0; position < 20; position++) {
            cmd.arg = position;
            check(&mrq, position < sectors && blocks <= sectors - position);
        }
        cmd.arg = 0;
        for (unsigned size = 0; size < 1025; size++) { data.blksz = size; check(&mrq, size == 512); }
        data.blksz = 512;
        for (unsigned bit = 0; bit < 32; bit++) { cmd.flags = read_flags ^ (1U << bit); check(&mrq, false); }
        cmd.flags = read_flags;
        mrq.sbc = &sbc; check(&mrq, false); mrq.sbc = NULL;
        if (blocks > 1) {
            for (unsigned opcode = 0; opcode < 64; opcode++) { stop.opcode = opcode; check(&mrq, opcode == MMC_STOP_TRANSMISSION); }
            stop.opcode = MMC_STOP_TRANSMISSION;
            for (unsigned bit = 0; bit < 32; bit++) {
                stop.arg = 1U << bit; check(&mrq, false); stop.arg = 0;
                stop.flags = stop_flags ^ (1U << bit); check(&mrq, false); stop.flags = stop_flags;
            }
            stop.data = &data; check(&mrq, false); stop.data = NULL;
            data.stop = NULL; check(&mrq, false); data.stop = &stop;
            mrq.stop = NULL; check(&mrq, false); mrq.stop = &stop;
        }
    }
    data.blocks = 1; cmd.opcode = MMC_READ_SINGLE_BLOCK; mrq.stop = data.stop = NULL;
    cmd.arg = 0; addressed = false; check(&mrq, false); addressed = true;
    sectors = 0; check(&mrq, false);
    sectors = (1ULL << 32) + 1; check(&mrq, false);
    sectors = 1ULL << 32; cmd.arg = 0xffffffffU; check(&mrq, true);
    sectors = 8; cmd.arg = 8; check(&mrq, false); cmd.arg = 7; check(&mrq, true);
    cmd.arg = 0;
    card_missing = true; check(&mrq, false); card_missing = false;
    slot_missing = true; check(&mrq, false); slot_missing = false;
    card_sd = false; check(&mrq, false); card_sd = true;
    card_read_bits = 10; check(&mrq, false); card_read_bits = 9;
    cmd.data = mrq.data = NULL; cmd.opcode = MMC_STOP_TRANSMISSION; cmd.arg = 0; cmd.flags = stop_flags;
    check(&mrq, true);
    cmd.flags = MMC_RSP_R1B | MMC_CMD_AC; check(&mrq, false);
    struct mmc_request empty = {0}; assert(hi3798mv100_sd_ro_request(&empty, true, 8) == -EPERM);
    puts("SD_RO_POLICY_QUEUE_PASS: all commands/directions, page-bounded sector reads, end-of-card, STOP and flags; writes/erase/settings rejected before hardware");
}
'''

RO_HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
struct dw_mci_drv_data { bool force_ro; };
struct dw_mci { const struct dw_mci_drv_data *drv_data; unsigned regs; };
struct dw_mci_slot { struct dw_mci *host; unsigned id; };
struct mmc_host { struct dw_mci_slot *slot; int gpio; int class_dev; };
static unsigned gpio_calls, reads;
#define mmc_priv(mmc) ((mmc)->slot)
#define mci_readl(host, reg) (reads++, (host)->regs)
#define dev_dbg(...) ((void)0)
static int mmc_gpio_get_ro(struct mmc_host *mmc) { gpio_calls++; return mmc->gpio; }
/* RO */
int main(void) {
    struct dw_mci_drv_data driver = {.force_ro = true};
    struct dw_mci host = {.drv_data = &driver};
    struct dw_mci_slot slot = {.host = &host};
    struct mmc_host mmc = {.slot = &slot, .gpio = -1};
    for (unsigned value = 0; value < 256; value++) {
        host.regs = value;
        assert(dw_mci_get_ro(&mmc) == 1 && !gpio_calls && !reads);
    }
    driver.force_ro = false;
    host.regs = 0; assert(!dw_mci_get_ro(&mmc));
    host.regs = 1; assert(dw_mci_get_ro(&mmc) == 1);
    mmc.gpio = 0; assert(!dw_mci_get_ro(&mmc));
    mmc.gpio = 1; assert(dw_mci_get_ro(&mmc) == 1);
    puts("SD_RO_FORCED_RO_PASS: actual callback overrides GPIO/register without reads; other hosts unchanged");
}
'''


def test(linuxsrc):
    project = Path(__file__).resolve().parents[1]
    driver_path = "drivers/mmc/host/dw_mmc-hi3798mv100-sd-ident.c"
    driver = (linuxsrc / driver_path).read_text()
    assert driver == (project / "overlay" / driver_path).read_text()
    assert ".force_ro = IS_ENABLED(CONFIG_HI3798MV100_SD_READ_ONLY)" in driver
    validate = driver[driver.index("static int mv100_sd_ident_validate("):driver.index("static int mv100_sd_ident_voltage(")]
    prefix = HARNESS[:HARNESS.index("int main(void)")]
    prefix = prefix.replace('#include "hi3798mv100-sd-ident-policy.h"',
                            '#include "hi3798mv100-sd-ro-policy.h"\nstatic bool addressed = true; static u64 sectors = 16;\n'
                            'static bool card_missing, slot_missing, card_sd = true; static unsigned card_read_bits = 9;\n'
                            '#define IS_ENABLED(option) 1\n#define dev_info_ratelimited(...) ((void)0)\n')
    prefix = prefix.replace("struct dw_mci;", "struct mmc_card { bool sd, blockaddr; struct { unsigned read_blkbits; u64 capacity; } csd; };\n"
                            "#define mmc_card_sd(card) ((card)->sd)\n"
                            "static bool mmc_card_is_blockaddr(struct mmc_card *card) { return card->blockaddr; }\n"
                            "struct dw_mci;")
    prefix = prefix.replace("int lock; };", "int lock; struct dw_mci_slot *slot; };")
    prefix = prefix.replace("struct dw_mci_slot { struct dw_mci *host; struct mmc_request *mrq; };",
                            "struct dw_mci_slot { struct dw_mci *host; struct mmc_request *mrq; struct mmc_host *mmc; };")
    prefix = prefix.replace("struct mmc_host { struct dw_mci_slot *slot; };",
                            "struct mmc_host { struct dw_mci_slot *slot; struct mmc_card *card; };")
    prefix = prefix.replace("static int validate(struct dw_mci *host, struct mmc_request *mrq)",
                            validate + "static int validate(struct dw_mci *host, struct mmc_request *mrq)")
    prefix = prefix.replace("return hi3798mv100_sd_ident_request(mrq);", "return mv100_sd_ident_validate(host, mrq);")
    prefix = prefix.replace("struct mmc_host mmc = { .slot = &slot };",
                            "struct mmc_card card = {.sd = card_sd, .blockaddr = addressed, .csd = {card_read_bits, sectors}};\n"
                            "    struct mmc_host mmc = { .slot = &slot, .card = card_missing ? NULL : &card };\n"
                            "    host.slot = slot_missing ? NULL : &slot; slot.mmc = &mmc;")
    prefix = prefix.replace("    assert(hi3798mv100_sd_ident_request(mrq) == (allowed ? 0 : -EPERM));\n", "")
    test_policy(linuxsrc, prefix + MAIN)
    source = (linuxsrc / "drivers/mmc/host/dw_mmc.c").read_text()
    ro = source[source.index("static int dw_mci_get_ro("):source.index("static void dw_mci_hw_reset(")]
    with tempfile.TemporaryDirectory(prefix="sd-ro-callback-") as directory:
        path = Path(directory)
        (path / "test.c").write_text(RO_HARNESS.replace("/* RO */", ro))
        binary = path / "test"
        subprocess.run(["cc", "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linuxsrc", type=Path, required=True)
    test(parser.parse_args().linuxsrc)
