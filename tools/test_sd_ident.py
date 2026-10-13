#!/usr/bin/env python3
"""Run actual SD metadata policy and DW queue entry with pinned MMC structures."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include "hi3798mv100-sd-ident-policy.h"
struct dw_mci;
struct dw_mci_drv_data { int (*validate_request)(struct dw_mci *, struct mmc_request *); };
struct dw_mci { const struct dw_mci_drv_data *drv_data; int lock; };
struct dw_mci_slot { struct dw_mci *host; struct mmc_request *mrq; };
struct mmc_host { struct dw_mci_slot *slot; };
static int queued, completed, presence_checked;
#define mmc_priv(mmc) ((mmc)->slot)
#define WARN_ON(test) assert(!(test))
#define spin_lock_bh(lock) ((void)(lock))
#define spin_unlock_bh(lock) ((void)(lock))
static int dw_mci_get_cd(struct mmc_host *mmc) { assert(mmc); presence_checked++; return 1; }
static void mmc_request_done(struct mmc_host *mmc, struct mmc_request *mrq) { assert(mmc && mrq); completed++; }
static void dw_mci_queue_request(struct dw_mci *host, struct dw_mci_slot *slot, struct mmc_request *mrq) { assert(host && slot && mrq); queued++; }
static int validate(struct dw_mci *host, struct mmc_request *mrq) { assert(host); return hi3798mv100_sd_ident_request(mrq); }
/* REQUEST */
static void check(struct mmc_request *mrq, bool allowed)
{
    static const struct dw_mci_drv_data data = { .validate_request = validate };
    struct dw_mci host = { .drv_data = &data };
    struct dw_mci_slot slot = { .host = &host };
    struct mmc_host mmc = { .slot = &slot };
    queued = completed = presence_checked = 0;
    mrq->cmd->error = 0;
    if (mrq->data) mrq->data->error = 0;
    assert(hi3798mv100_sd_ident_request(mrq) == (allowed ? 0 : -EPERM));
    dw_mci_request(&mmc, mrq);
    assert(queued == allowed && completed == !allowed && presence_checked == allowed);
    assert(mrq->cmd->error == (allowed ? 0 : -EPERM));
    if (mrq->data) assert(mrq->data->error == (allowed ? 0 : -EPERM));
}
int main(void)
{
    struct mmc_command cmd = {0}, side = {0};
    struct mmc_data data = {.flags = MMC_DATA_READ, .blocks = 1};
    struct mmc_request mrq = {.cmd = &cmd};
    for (unsigned opcode = 0; opcode < 64; opcode++) {
        cmd.opcode = opcode;
        cmd.arg = opcode == 8 ? 0x1aa : opcode == 9 || opcode == 10 || opcode == 13 ? 0x12340000 : 0;
        check(&mrq, opcode == 0 || opcode == 2 || opcode == 3 || opcode == 7 || opcode == 8 || opcode == 9 || opcode == 10 || opcode == 13 || opcode == 41 || opcode == 55);
        cmd.data = mrq.data = &data;
        for (unsigned direction = 1; direction <= 3; direction++) for (unsigned size = 1; size <= 513; size++) {
            data.flags = direction; data.blksz = size;
            cmd.arg = opcode == 6 ? 0x00fffff0 : 0;
            check(&mrq, direction == MMC_DATA_READ && ((opcode == 51 && size == 8) || ((opcode == 6 || opcode == 13) && size == 64)));
        }
        cmd.data = mrq.data = NULL;
    }
    data = (struct mmc_data){.flags = MMC_DATA_READ, .blocks = 1, .blksz = 64};
    cmd.opcode = SD_SWITCH; cmd.arg = 0x00fffff0; cmd.data = mrq.data = &data;
    check(&mrq, true);
    for (unsigned bit = 0; bit < 32; bit++) { cmd.arg = 0x00fffff0 ^ (1U << bit); check(&mrq, false); }
    cmd.arg = 0x00fffff0; data.blocks = 2; check(&mrq, false); data.blocks = 1;
    mrq.stop = &side; check(&mrq, false); mrq.stop = NULL;
    mrq.sbc = &side; check(&mrq, false); mrq.sbc = NULL;
    data.stop = &side; check(&mrq, false); data.stop = NULL;
    cmd.data = NULL; check(&mrq, false); cmd.data = &data; mrq.data = NULL; check(&mrq, false);
    cmd.data = NULL; cmd.opcode = SD_APP_OP_COND;
    for (unsigned bit = 0; bit < 32; bit++) { cmd.arg = 1U << bit; check(&mrq, !(cmd.arg & ~0x40ff8000U)); }
    cmd.arg = 0x40ff8000; check(&mrq, true);
    cmd.opcode = MMC_SELECT_CARD;
    for (unsigned rca = 0; rca < 65536; rca++) { cmd.arg = rca << 16; check(&mrq, true); cmd.arg |= 1; check(&mrq, false); }
    struct mmc_request empty = {0}; assert(hi3798mv100_sd_ident_request(&empty) == -EPERM);
    puts("SD_IDENT_POLICY_PASS: actual policy/queue, metadata-only direction/length, all opcodes, RCA/OCR, mutation and sidecar rejection");
}
'''


def test(linuxsrc, harness=HARNESS):
    driver = (linuxsrc / "drivers/mmc/host/dw_mmc.c").read_text()
    request = "static void dw_mci_request(" + driver.split("static void dw_mci_request(", 1)[1].split("\nstatic void dw_mci_set_ios", 1)[0]
    assert request.index("validate_request(host, mrq)") < request.index("dw_mci_get_cd(mmc)") < request.index("dw_mci_queue_request(host, slot, mrq)")
    sd = (linuxsrc / "drivers/mmc/core/sd.c").read_text()
    switch = sd[sd.index("static int mmc_read_switch("):sd.index("int mmc_sd_switch_hs(")]
    assert "mmc_sd_switch(card, SD_SWITCH_CHECK, 0, 0, status)" in switch
    extension = sd[sd.index("static int sd_read_ext_regs("):sd.index("static bool sd_cache_enabled(")]
    assert extension.index("IS_ENABLED(CONFIG_MMC_DW_HI3798MV100_SD_IDENT)") < extension.index("sd_read_ext_reg(card")
    with tempfile.TemporaryDirectory(prefix="sd-ident-policy-") as directory:
        path = Path(directory)
        (path / "linux/mmc").mkdir(parents=True)
        (path / "asm-generic").mkdir()
        for name in ("core.h", "mmc.h", "sd.h"):
            shutil.copyfile(linuxsrc / "include/linux/mmc" / name, path / "linux/mmc" / name)
        for name in ("errno.h", "errno-base.h"):
            shutil.copyfile(linuxsrc / "include/uapi/asm-generic" / name, path / "asm-generic" / name)
        (path / "linux/errno.h").write_text('#include <asm-generic/errno.h>\n')
        (path / "linux/types.h").write_text('#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\ntypedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64; typedef int32_t s32;\n#define BIT(n) (1U << (n))\n')
        (path / "linux/completion.h").write_text('struct completion { int unused; };\n')
        (path / "test.c").write_text(harness.replace("/* REQUEST */", request))
        binary = path / "test"
        subprocess.run(["cc", "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I", str(path),
                        "-I", str(ROOT / "overlay/drivers/mmc/host"), str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linuxsrc", type=Path, required=True)
    args = parser.parse_args()
    test(args.linuxsrc)
