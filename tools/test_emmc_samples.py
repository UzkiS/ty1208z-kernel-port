#!/usr/bin/env python3
"""Execute the actual fixed-sector probe with queue/error/allocation instrumentation."""
import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--linuxsrc", type=Path, required=True)
args = parser.parse_args()
driver = (ROOT / "overlay/drivers/mmc/core/ty1208z-samples.c").read_text()
actual = "static int ty1208z_read_sector(" + driver.split(
    "static int ty1208z_read_sector(", 1)[1].split("\nstatic void ty1208z_samples_remove", 1)[0]

# Synthetic, non-firmware header with a solved four-byte CRC suffix. Exercise
# the real checksum comparison without distributing any of the user's image.
fixture = bytearray(512)
struct.pack_into(">I", fixture, 0, 0x27051956)
struct.pack_into(">II", fixture, 16, 0x02000000, 0x02000000)
base = zlib.crc32(fixture)
basis = {}
for bit in range(32):
    sample = fixture.copy()
    struct.pack_into("<I", sample, 508, 1 << bit)
    vector, mask = zlib.crc32(sample) ^ base, 1 << bit
    while vector:
        pivot = vector.bit_length() - 1
        if pivot not in basis:
            basis[pivot] = (vector, mask)
            break
        vector ^= basis[pivot][0]
        mask ^= basis[pivot][1]
target, suffix = 0x2BA1A125 ^ base, 0
while target:
    vector, mask = basis[target.bit_length() - 1]
    target ^= vector
    suffix ^= mask
struct.pack_into("<I", fixture, 508, suffix)
assert zlib.crc32(fixture) == 0x2BA1A125

harness = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "hi3798mv100-ident-policy.h"
#define MMC_BUS_WIDTH_1 0
#define MMC_TIMING_LEGACY 0
#define GFP_KERNEL 0
#define dev_info(...) ((void)0)
#define dev_err(...) ((void)0)
struct mmc_host { struct { unsigned int bus_width, timing, clock; } ios; };
struct mmc_card {
    struct mmc_host *host;
    struct { char prod_name[8]; unsigned int manfid; } cid;
    struct { unsigned int sectors, part_config; } ext_csd;
    int type, blockaddr;
};
struct scatterlist { void *buffer; unsigned int length; };
static int claims, allocations, calls, fail_call, fail_kind, bad_metadata, alloc_fail;
static const u8 fixture[512] = { /* FIXTURE */ };
static const u32 expected[] = {28672, 28673, 1249282, 1249283};
static int mmc_card_mmc(struct mmc_card *card) { return card->type == 0; }
static int mmc_card_is_blockaddr(struct mmc_card *card) { return card->blockaddr; }
static void mmc_claim_host(struct mmc_host *host) { (void)host; assert(!claims++); }
static void mmc_release_host(struct mmc_host *host) { (void)host; assert(claims-- == 1); }
static void *kmalloc(size_t size, int flags) {
    (void)flags;
    if (alloc_fail) return NULL;
    allocations++; return calloc(1, size);
}
static void kfree(void *ptr) { assert(allocations-- == 1); free(ptr); }
static void sg_init_one(struct scatterlist *sg, void *buffer, unsigned int length) {
    sg->buffer = buffer; sg->length = length;
}
void mmc_set_data_timeout(struct mmc_data *data, const struct mmc_card *card) {
    (void)card; data->timeout_ns = 1000000;
}
static u32 crc32_le(u32 crc, const u8 *buffer, size_t length) {
    while (length--) {
        crc ^= *buffer++;
        for (int bit = 0; bit < 8; bit++) crc = (crc >> 1) ^ (0xedb88320U & -(crc & 1));
    }
    return crc;
}
static u32 get_unaligned_be32(const u8 *p) {
    return (u32)p[0] << 24 | (u32)p[1] << 16 | (u32)p[2] << 8 | p[3];
}
static u32 get_unaligned_le32(const u8 *p) {
    return (u32)p[3] << 24 | (u32)p[2] << 16 | (u32)p[1] << 8 | p[0];
}
static u16 get_unaligned_le16(const u8 *p) { return (u16)p[1] << 8 | p[0]; }
void mmc_wait_for_req(struct mmc_host *host, struct mmc_request *mrq) {
    (void)host;
    assert(claims == 1 && calls < 4);
    assert(hi3798mv100_ident_request(mrq) == 0);
    assert(!mrq->sbc && !mrq->stop && !mrq->data->stop);
    assert(mrq->cmd->opcode == MMC_READ_SINGLE_BLOCK && mrq->cmd->arg == expected[calls]);
    assert(mrq->cmd->flags == (MMC_RSP_R1 | MMC_CMD_ADTC));
    assert(mrq->data->flags == MMC_DATA_READ && mrq->data->blocks == 1 && mrq->data->blksz == 512);
    assert(mrq->data->sg_len == 1 && mrq->data->sg->length == 512);
    u8 *p = mrq->data->sg->buffer;
    memset(p, 0, 512);
    if (calls == 0) {
        memcpy(p, fixture, 512);
        if (bad_metadata == 1) p[100] ^= 1;
    } else if (calls == 2) {
        p[0] = 1; p[4] = 1; p[24] = bad_metadata == 3 ? 7 : 2;
        p[56] = bad_metadata == 2 ? 0 : 0x53; p[57] = 0xef;
    }
    calls++;
    mrq->data->bytes_xfered = 512;
    if (calls == fail_call) {
        if (fail_kind == 1) mrq->cmd->error = -EIO;
        if (fail_kind == 2) mrq->data->error = -EIO;
        if (fail_kind == 3) mrq->data->bytes_xfered = 511;
        if (fail_kind == 4) mrq->cmd->resp[0] = R1_ILLEGAL_COMMAND;
    }
}
/* ACTUAL */
int main(void) {
    struct mmc_host host = {.ios = {.clock = 25000000}};
    struct mmc_card original = {.host = &host, .cid = {.prod_name = "008G30", .manfid = 0x11},
                               .ext_csd = {.sectors = 15269888}, .blockaddr = 1};
    assert((crc32_le(~0U, fixture, 512) ^ ~0U) == 0x2ba1a125);
    for (int invalid = 0; invalid < 9; invalid++) {
        struct mmc_card card = original;
        struct mmc_host changed = host; card.host = &changed;
        if (invalid == 0) card.type = 1;
        if (invalid == 1) card.blockaddr = 0;
        if (invalid == 2) card.cid.prod_name[0] = 'X';
        if (invalid == 3) card.cid.manfid = 0;
        if (invalid == 4) card.ext_csd.sectors++;
        if (invalid == 5) card.ext_csd.part_config = 1;
        if (invalid == 6) changed.ios.bus_width = 1;
        if (invalid == 7) changed.ios.timing = 1;
        if (invalid == 8) changed.ios.clock++;
        calls = 0;
        assert(ty1208z_samples_probe(&card) == -ENODEV && !calls && !claims && !allocations);
    }
    alloc_fail = 1;
    assert(ty1208z_samples_probe(&original) == -ENOMEM && !calls && !claims && !allocations);
    alloc_fail = 0;
    assert(ty1208z_samples_probe(&original) == 0 && calls == 4 && !claims && !allocations);
    for (fail_kind = 1; fail_kind <= 4; fail_kind++) {
        for (fail_call = 1; fail_call <= 4; fail_call++) {
            calls = 0;
            assert(ty1208z_samples_probe(&original) == -EIO);
            assert(calls == fail_call && !claims && !allocations);
        }
    }
    fail_call = 0;
    for (bad_metadata = 1; bad_metadata <= 3; bad_metadata++) {
        calls = 0;
        assert(ty1208z_samples_probe(&original) == -EBADMSG);
        assert(calls == (bad_metadata == 1 ? 1 : 4) && !claims && !allocations);
    }
    puts("EMMC_SAMPLES_PASS: actual probe, four fixed CMD17 reads; wrong cards and failed/short/error reads stop cleanly");
}
'''.replace("/* ACTUAL */", actual).replace("/* FIXTURE */", ",".join(map(str, fixture)))

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "linux/mmc").mkdir(parents=True)
    (temp / "asm-generic").mkdir()
    for name in ("core.h", "mmc.h"):
        shutil.copyfile(args.linuxsrc / "include/linux/mmc" / name, temp / "linux/mmc" / name)
    shutil.copyfile(ROOT / "overlay/include/linux/mmc/ty1208z-samples.h", temp / "linux/mmc/ty1208z-samples.h")
    for name in ("errno.h", "errno-base.h"):
        shutil.copyfile(args.linuxsrc / "include/uapi/asm-generic" / name, temp / "asm-generic" / name)
    (temp / "linux/errno.h").write_text('#include <asm-generic/errno.h>\n')
    (temp / "linux/types.h").write_text(
        '#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n'
        'typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;\n'
        'typedef uint64_t u64; typedef int32_t s32;\n#define BIT(n) (1U << (n))\n')
    (temp / "linux/completion.h").write_text('struct completion { int unused; };\n')
    (temp / "harness.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(temp),
                    "-I", str(ROOT / "overlay/drivers/mmc/host"),
                    "-DCONFIG_HI3798MV100_EMMC_READ_SAMPLES=1", str(temp / "harness.c"),
                    "-o", str(temp / "test")], check=True)
    subprocess.run([str(temp / "test")], check=True)
