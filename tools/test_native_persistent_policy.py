#!/usr/bin/env python3
"""Test real p6/p9 request limits and block readonly behavior under sanitizers."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from native_persistent_patch import ensure

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include "hi3798mv100-emmc-install-policy.h"
#define IS_ENABLED(option) (option)
struct mmc_host { unsigned max_blk_count, max_req_size; };
struct mmc_card { bool mmc, ro; struct { unsigned cmdclass; } csd; struct mmc_host *host; };
#define mmc_card_mmc(card) ((card)->mmc)
#define mmc_card_readonly(card) ((card)->ro)
/* READONLY */
/* SWITCH_PREP */
#define PAGE_SIZE 4096U
#define min(a,b) ((a) < (b) ? (a) : (b))
#define max(a,b) ((a) > (b) ? (a) : (b))
static unsigned queue_limit(struct mmc_card *card) {
    struct mmc_host *host = card->host;
    struct { unsigned max_hw_sectors; } lim;
    /* QUEUE_LIMIT */
    return lim.max_hw_sectors;
}
static unsigned transfer_blocks(struct mmc_card *card, unsigned requested) {
    struct { struct { unsigned blocks; } data; } request = {.data.blocks = requested}, *brq = &request;
    /* TRANSFER_LIMIT */
    return brq->data.blocks;
}
int main(void) {
    struct mmc_host host = {.max_blk_count = 1, .max_req_size = PAGE_SIZE};
    struct mmc_card card = {.mmc = true, .csd.cmdclass = CCC_BLOCK_WRITE, .host = &host};
    assert(queue_limit(&card) == (CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE ? 8U : 1U));
    assert(transfer_blocks(&card, 8) == 1);
    card.mmc = false; assert(queue_limit(&card) == 1); card.mmc = true;
    host.max_blk_count = 8; assert(queue_limit(&card) == 8); host.max_blk_count = 1;
    assert(!!mmc_blk_readonly(&card) == !CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE);
    card.ro = true; assert(mmc_blk_readonly(&card)); card.ro = false;
    card.mmc = false; assert(mmc_blk_readonly(&card));
    struct mmc_command cmd = {.opcode = MMC_WRITE_BLOCK,
        .flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC};
    struct mmc_data data = {.blksz = 512, .blocks = 1, .flags = MMC_DATA_WRITE};
    struct mmc_request mrq = {.cmd = &cmd, .data = &data}; cmd.data = &data;
    unsigned sectors[] = {0, 2048, 28671, 28672, 69631, 69632,
                          1249279, 1249280, 15269887, 15269888, 0xffffffff};
    for (unsigned i = 0; i < sizeof(sectors)/sizeof(sectors[0]); i++) {
        cmd.arg = sectors[i];
        bool allowed = (cmd.arg >= 28672 && cmd.arg < 69632) ||
                       (cmd.arg >= 1249280 && cmd.arg < 15269888);
        assert((hi3798mv100_emmc_install_request(&mrq, true, 15269888) == 0) == allowed);
        assert(hi3798mv100_emmc_ro_request(&mrq, true, 15269888) == -EPERM);
    }
    cmd.arg = 1249280;
    assert(hi3798mv100_emmc_install_request(&mrq, false, 15269888) == -EPERM);
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269887) == -EPERM);
    data.blocks = 2; assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == -EPERM);
    data.blocks = 1; data.flags |= MMC_DATA_READ;
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == -EPERM);
    data.flags = MMC_DATA_WRITE; mrq.sbc = &cmd;
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == -EPERM);
    mrq.sbc = NULL; mrq.stop = &cmd;
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == -EPERM);
    mrq.stop = NULL; cmd.flags |= MMC_RSP_BUSY;
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == -EPERM);
    cmd.data = mrq.data = NULL;
    cmd = prepare_switch(EXT_CSD_CMD_SET_NORMAL, EXT_CSD_FLUSH_CACHE, 1);
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == 0);
    cmd = prepare_switch(EXT_CSD_CMD_SET_NORMAL, EXT_CSD_CACHE_CTRL, 0);
    assert(hi3798mv100_emmc_install_request(&mrq, false, 0) == 0);
    cmd = prepare_switch(EXT_CSD_CMD_SET_NORMAL, EXT_CSD_CACHE_CTRL, 1);
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == 0);
    assert(hi3798mv100_emmc_install_request(&mrq, false, 0) != 0);
    cmd.flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC;
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) == 0);
    cmd.arg += (1 << 8);
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) != 0);
    cmd.arg = (MMC_SWITCH_MODE_WRITE_BYTE << 24) | (EXT_CSD_PART_CONFIG << 16) | (1 << 8);
    assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) != 0);
    for (unsigned op = 0; op < 64; op++) {
        cmd.opcode = op; cmd.arg = 0xffffffff;
        assert(hi3798mv100_emmc_install_request(&mrq, true, 15269888) != 0);
    }
    puts("NATIVE_PERSISTENT_POLICY_PASS");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linuxsrc", type=Path, required=True)
    parser.add_argument("--ram-artifacts", type=Path)
    args = parser.parse_args()
    source = args.linuxsrc
    ops = (source / "drivers/mmc/core/mmc_ops.c").read_text()
    switch = ops[ops.index("int __mmc_switch("):]
    start = switch.index("\tcmd.opcode = MMC_SWITCH;")
    end = switch.index("\tuse_r1b_resp =", start)
    switch_prep = ('static struct mmc_command prepare_switch(u8 set, u8 index, u8 value) {\n'
                   'struct mmc_command cmd = {0};\n' + switch[start:end] +
                   'cmd.flags = MMC_RSP_SPI_R1B | MMC_RSP_R1B | MMC_CMD_AC; return cmd; }\n')
    if args.ram_artifacts:
        from inspect_images import parse_fdt
        from native_system_profile import native_system_profile
        artifacts = args.ram_artifacts
        tree = parse_fdt((artifacts / "ty1208z-diagnostic.dtb").read_bytes())
        config = (artifacts / "linux.config").read_text()
        assert native_system_profile(tree, config)
        candidate = config + "\nCONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE=y\n"
        try:
            native_system_profile(tree, candidate)
        except ValueError:
            pass
        else:
            raise AssertionError("Read-only boot mode accepted a write-capable kernel")
        assert native_system_profile(tree, candidate, allow_install_candidate=True)
    block = ensure((source / "drivers/mmc/core/block.c").read_text(), "drivers/mmc/core/block.c")
    queue = ensure((source / "drivers/mmc/core/queue.c").read_text(), "drivers/mmc/core/queue.c")
    start = queue.index("\tlim.max_hw_sectors = min(")
    queue_limit = queue[start:queue.index("\n\n", start)]
    start = block.index("\tif (brq->data.blocks > card->host->max_blk_count)")
    transfer_limit = block[start:block.index("\n\n", start)]
    start = block.index("static inline int mmc_blk_readonly(")
    readonly = block[start:block.index("\n}\n", start) + 3]
    with tempfile.TemporaryDirectory(prefix="emmc-install-") as directory:
        temp = Path(directory)
        (temp / "linux/mmc").mkdir(parents=True)
        (temp / "asm-generic").mkdir()
        for name in ("core.h", "mmc.h"):
            shutil.copyfile(source / "include/linux/mmc" / name, temp / "linux/mmc" / name)
        shutil.copyfile(ROOT / "overlay/include/linux/mmc/ty1208z-samples.h", temp / "linux/mmc/ty1208z-samples.h")
        for name in ("errno.h", "errno-base.h"):
            shutil.copyfile(source / "include/uapi/asm-generic" / name, temp / "asm-generic" / name)
        (temp / "linux/errno.h").write_text('#include <asm-generic/errno.h>\n')
        (temp / "linux/types.h").write_text('#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n'
                                          'typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;\n'
                                          'typedef uint64_t u64; typedef int32_t s32;\n#define BIT(n) (1U << (n))\n')
        (temp / "linux/completion.h").write_text('struct completion { int unused; };\n')
        harness = temp / "test.c"
        harness.write_text(HARNESS.replace("/* READONLY */", readonly).replace("/* SWITCH_PREP */", switch_prep)
                           .replace("/* QUEUE_LIMIT */", queue_limit).replace("/* TRANSFER_LIMIT */", transfer_limit))
        for enabled in (0, 1):
            binary = temp / f"test-{enabled}"
            subprocess.run(["cc", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I", str(temp),
                            "-I", str(ROOT / "overlay/drivers/mmc/host"),
                            "-DCONFIG_HI3798MV100_EMMC_READ_ONLY=1",
                            f"-DCONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE={enabled}",
                            str(harness), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
