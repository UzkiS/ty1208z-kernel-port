#!/usr/bin/env python3
"""Execute the real request policy and patched queue entry with a mock host."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--linuxsrc", type=Path, required=True)
args = parser.parse_args()
source = args.linuxsrc
driver = (source / "drivers/mmc/host/dw_mmc.c").read_text()
request = driver.split("static void dw_mci_request(", 1)[1].split("\nstatic void dw_mci_set_ios", 1)[0]
request = "static void dw_mci_request(" + request
assert request.index("validate_request(host, mrq)") < request.index("dw_mci_get_cd(mmc)")
assert request.index("validate_request(host, mrq)") < request.index("dw_mci_queue_request(host, slot, mrq)")
dma = driver.split("static void dw_mci_init_dma(", 1)[1].split("\nstatic void dw_mci_cmd11_timer", 1)[0]
assert dma.index("force_pio") < dma.index("SDMMC_GET_TRANS_MODE") < dma.index("dmam_alloc_coherent")
slot = driver.split("static int dw_mci_init_slot(", 1)[1].split("\nstatic void dw_mci_cleanup_slot", 1)[0]
assert slot.index("init_slot(slot)") < slot.index("mmc_add_host(mmc)")
assert slot.index("mmc->max_blk_count = 512;") < slot.index("init_slot(slot)")
probe = driver.split("int dw_mci_probe(", 1)[1].split("EXPORT_SYMBOL(dw_mci_probe)", 1)[0]
assert probe.index("drv_data->init(host)") < probe.index("dw_mci_ctrl_reset(host")

harness = r'''
#include <assert.h>
#include <stdio.h>
#include "hi3798mv100-ident-policy.h"
struct dw_mci;
struct dw_mci_drv_data {
    int (*validate_request)(struct dw_mci *, struct mmc_request *);
};
struct dw_mci { const struct dw_mci_drv_data *drv_data; int lock; };
struct dw_mci_slot { struct dw_mci *host; struct mmc_request *mrq; };
struct mmc_host { struct dw_mci_slot *slot; };
static int queued, completed, presence_checked;
#define mmc_priv(mmc) ((mmc)->slot)
#define WARN_ON(test) assert(!(test))
#define spin_lock_bh(lock) ((void)(lock))
#define spin_unlock_bh(lock) ((void)(lock))
static int dw_mci_get_cd(struct mmc_host *mmc) {
    (void)mmc; presence_checked++; return 1;
}
static void mmc_request_done(struct mmc_host *mmc, struct mmc_request *mrq) {
    (void)mmc; (void)mrq; completed++;
}
static void dw_mci_queue_request(struct dw_mci *host, struct dw_mci_slot *slot,
                                struct mmc_request *mrq) {
    (void)host; (void)slot; (void)mrq; queued++;
}
static int validate(struct dw_mci *host, struct mmc_request *mrq) {
    (void)host; return hi3798mv100_ident_request(mrq);
}
/* PATCHED_REQUEST */
static void check(struct mmc_request *mrq, int expected) {
    static const struct dw_mci_drv_data data = { .validate_request = validate };
    struct dw_mci host = { .drv_data = &data };
    struct dw_mci_slot slot = { .host = &host };
    struct mmc_host mmc = { .slot = &slot };
    queued = completed = presence_checked = 0;
    mrq->cmd->error = 0;
    if (mrq->data) mrq->data->error = 0;
    assert(hi3798mv100_ident_request(mrq) == expected);
    dw_mci_request(&mmc, mrq);
    assert(queued == !expected && completed == !!expected);
    assert(presence_checked == !expected);
    assert(mrq->cmd->error == expected);
    if (mrq->data) assert(mrq->data->error == expected);
}
int main(void) {
    struct mmc_command cmd = {0}, secondary = {0};
    struct mmc_data data = {.flags = MMC_DATA_READ, .blocks = 1, .blksz = 512};
    struct mmc_request mrq = {.cmd = &cmd};
    for (unsigned int opcode = 0; opcode < 64; opcode++) {
        cmd.opcode = opcode;
        cmd.arg = (opcode == 3 || opcode == 9 || opcode == 10 || opcode == 13)
                  ? 0x10000 : 0;
        int allowed = opcode == 0 || opcode == 1 || opcode == 2 || opcode == 3 ||
                      opcode == 7 || opcode == 9 || opcode == 10 || opcode == 13;
        check(&mrq, opcode == 6 ? -EBADMSG : allowed ? 0 : -EPERM);
        /* Every command with write data must fail before queue/presence access. */
        cmd.data = mrq.data = &data;
        data.flags = MMC_DATA_WRITE;
        check(&mrq, -EPERM);
        data.flags = MMC_DATA_READ;
        check(&mrq, opcode == 8 ? 0 : -EPERM);
        cmd.data = mrq.data = NULL;
    }
    cmd.opcode = MMC_SEND_EXT_CSD; cmd.arg = 0;
    cmd.data = mrq.data = &data;
    check(&mrq, 0);
    data.flags = MMC_DATA_READ | MMC_DATA_WRITE; check(&mrq, -EPERM);
    data.flags = MMC_DATA_READ; data.blocks = 2; check(&mrq, -EPERM);
    data.blocks = 1; data.blksz = 1024; check(&mrq, -EPERM);
    data.blksz = 512; cmd.arg = 1; check(&mrq, -EPERM);
    cmd.arg = 0; mrq.sbc = &secondary; check(&mrq, -EPERM);
    mrq.sbc = NULL; mrq.stop = &secondary; check(&mrq, -EPERM);
    mrq.stop = NULL; data.stop = &secondary; check(&mrq, -EPERM);
    data.stop = NULL; cmd.data = NULL; check(&mrq, -EPERM);
    cmd.data = &data; mrq.data = NULL; check(&mrq, -EPERM);
    cmd.data = NULL;
    cmd.opcode = MMC_SEND_OP_COND;
    cmd.arg = 0x40ff8000; check(&mrq, 0);
    cmd.arg = 0x80000000; check(&mrq, -EPERM);
    cmd.opcode = MMC_GO_IDLE_STATE;
    cmd.arg = 0xf0f0f0f0; check(&mrq, -EPERM); /* pre-idle/boot variants */
    cmd.opcode = MMC_SEND_STATUS;
    cmd.arg = 0x10001; check(&mrq, -EPERM); /* HPI bit */
    cmd.opcode = MMC_SELECT_CARD;
    cmd.arg = 0x20000; check(&mrq, -EPERM);
    cmd.arg = 0x10000; check(&mrq, 0);
    cmd.opcode = MMC_SWITCH; cmd.arg = 0xffffffff; check(&mrq, -EBADMSG);
    /* Other platforms with no hook must retain their normal queue behavior. */
    struct dw_mci host = {0};
    struct dw_mci_slot unfiltered = {.host = &host};
    struct mmc_host mmc = {.slot = &unfiltered};
    queued = completed = presence_checked = 0;
    dw_mci_request(&mmc, &mrq);
    assert(queued == 1 && completed == 0 && presence_checked == 1);
    puts("EMMC_IDENT_POLICY_PASS: real policy/queue entry, 64 opcodes, malformed/sidecar requests");
}
'''.replace("/* PATCHED_REQUEST */", request)

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "linux/mmc").mkdir(parents=True)
    (temp / "asm-generic").mkdir()
    # Use the real pinned MMC structures/opcode constants, not a rewritten model.
    for name in ("core.h", "mmc.h"):
        shutil.copyfile(source / "include/linux/mmc" / name, temp / "linux/mmc" / name)
    for name in ("errno.h", "errno-base.h"):
        shutil.copyfile(source / "include/uapi/asm-generic" / name, temp / "asm-generic" / name)
    (temp / "linux/errno.h").write_text('#include <asm-generic/errno.h>\n')
    (temp / "linux/types.h").write_text(
        '#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n'
        'typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;\n'
        'typedef uint64_t u64; typedef int32_t s32;\n#define BIT(n) (1U << (n))\n')
    (temp / "linux/completion.h").write_text('struct completion { int unused; };\n')
    (temp / "harness.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(temp),
                    "-I", str(ROOT / "overlay/drivers/mmc/host"), str(temp / "harness.c"),
                    "-o", str(temp / "test")], check=True)
    subprocess.run([str(temp / "test")], check=True)
print("Source ordering passed: identity/init, request rejection, PIO and final slot limits")
