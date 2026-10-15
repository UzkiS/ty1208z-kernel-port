#!/usr/bin/env python3
"""Exercise actual eMMC RO validation, queue, slot and block-core gates."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "hi3798mv100-emmc-ro-policy.h"
#define IS_ENABLED(option) (option)
#define dev_info_ratelimited(...) ((void)0)
/* HOST_CAPS */
struct mmc_card {
    bool mmc, blockaddr;
    struct { unsigned read_blkbits; } csd;
    struct { char prod_name[8]; } cid;
    struct { unsigned rev, data_sector_size, part_config; u64 sectors; } ext_csd;
};
#define mmc_card_mmc(card) ((card)->mmc)
#define mmc_card_is_blockaddr(card) ((card)->blockaddr)
struct dw_mci;
struct dw_mci_drv_data {
    int (*validate_request)(struct dw_mci *, struct mmc_request *);
};
struct dw_mci { const struct dw_mci_drv_data *drv_data; int lock; struct dw_mci_slot *slot; };
struct dw_mci_slot { struct dw_mci *host; struct mmc_request *mrq; struct mmc_host *mmc; };
struct mmc_host {
    struct dw_mci_slot *slot;
    struct mmc_card *card;
    unsigned caps, caps2, pm_caps, f_max, max_blk_size, max_blk_count;
    unsigned max_req_size, max_seg_size, dsr_req;
};
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
/* SLOT */
/* VALIDATE */
/* QUEUE */
static void check(struct mmc_card *card, struct mmc_request *mrq, int expected) {
    const struct dw_mci_drv_data driver = {.validate_request = mv100_ident_validate};
    struct dw_mci host = {.drv_data = &driver};
    struct dw_mci_slot slot = {.host = &host};
    struct mmc_host mmc = {.slot = &slot, .card = card};
    slot.mmc = &mmc; host.slot = &slot;
    queued = completed = presence_checked = 0;
    mrq->cmd->error = 0;
    if (mrq->data) mrq->data->error = 0;
    assert(mv100_ident_validate(&host, mrq) == expected);
    dw_mci_request(&mmc, mrq);
    assert(queued == !expected && completed == !!expected);
    assert(presence_checked == !expected && mrq->cmd->error == expected);
    if (mrq->data) assert(mrq->data->error == expected);
}
int main(void) {
    struct mmc_card card = {.mmc = true, .blockaddr = true,
        .csd = {.read_blkbits = 9}, .cid = {.prod_name = "008G30"},
        .ext_csd = {.rev = 8, .data_sector_size = 512, .sectors = 15269888}};
    struct mmc_command cmd = {0}, stop = {0}, sbc = {0};
    struct mmc_data data = {.flags = MMC_DATA_READ, .blksz = 512, .blocks = 1};
    struct mmc_request mrq = {.cmd = &cmd, .data = &data};
    const unsigned read_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
    const unsigned stop_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC;
    cmd.data = &data; cmd.flags = read_flags;
    stop.opcode = MMC_STOP_TRANSMISSION; stop.flags = stop_flags;
    for (unsigned opcode = 0; opcode < 64; opcode++) {
        cmd.opcode = opcode; cmd.arg = 0;
        for (unsigned blocks = 1; blocks < 11; blocks++) {
            data.blocks = blocks; data.stop = mrq.stop = blocks > 1 ? &stop : NULL;
            for (unsigned direction = 0; direction < 4; direction++) {
                data.flags = direction;
                bool allowed = direction == MMC_DATA_READ && blocks <= 8 &&
                    (opcode == (blocks == 1 ? MMC_READ_SINGLE_BLOCK : MMC_READ_MULTIPLE_BLOCK) ||
                     (blocks == 1 && opcode == MMC_SEND_EXT_CSD));
                check(&card, &mrq, allowed ? 0 : -EPERM);
            }
        }
    }
    data.flags = MMC_DATA_READ;
    for (unsigned blocks = 1; blocks <= 8; blocks++) {
        data.blocks = blocks;
        cmd.opcode = blocks == 1 ? MMC_READ_SINGLE_BLOCK : MMC_READ_MULTIPLE_BLOCK;
        data.stop = mrq.stop = blocks > 1 ? &stop : NULL;
        for (unsigned end = 0; end < 20; end++) {
            cmd.arg = 15269888 - end;
            check(&card, &mrq, end >= blocks ? 0 : -EPERM);
        }
        cmd.arg = 0xffffffffU; check(&card, &mrq, -EPERM); cmd.arg = 0;
        for (unsigned size = 0; size < 1025; size++) {
            data.blksz = size; check(&card, &mrq, size == 512 ? 0 : -EPERM);
        }
        data.blksz = 512;
        for (unsigned bit = 0; bit < 32; bit++) {
            cmd.flags = read_flags ^ (1U << bit); check(&card, &mrq, -EPERM);
        }
        cmd.flags = read_flags;
        mrq.sbc = &sbc; check(&card, &mrq, -EPERM); mrq.sbc = NULL;
        if (blocks > 1) {
            for (unsigned opcode = 0; opcode < 64; opcode++) {
                stop.opcode = opcode;
                check(&card, &mrq, opcode == MMC_STOP_TRANSMISSION ? 0 : -EPERM);
            }
            stop.opcode = MMC_STOP_TRANSMISSION;
            for (unsigned bit = 0; bit < 32; bit++) {
                stop.arg = 1U << bit; check(&card, &mrq, -EPERM); stop.arg = 0;
                stop.flags = stop_flags ^ (1U << bit); check(&card, &mrq, -EPERM);
                stop.flags = stop_flags;
            }
            stop.data = &data; check(&card, &mrq, -EPERM); stop.data = NULL;
            data.stop = NULL; check(&card, &mrq, -EPERM); data.stop = &stop;
            mrq.stop = NULL; check(&card, &mrq, -EPERM); mrq.stop = &stop;
        }
    }
    data.blocks = 1; cmd.opcode = MMC_READ_SINGLE_BLOCK; mrq.stop = data.stop = NULL;
    check(&card, &mrq, 0);
    card.mmc = false; check(&card, &mrq, -EPERM); card.mmc = true;
    card.blockaddr = false; check(&card, &mrq, -EPERM); card.blockaddr = true;
    card.csd.read_blkbits = 10; check(&card, &mrq, -EPERM); card.csd.read_blkbits = 9;
    card.cid.prod_name[0] = '1'; check(&card, &mrq, -EPERM); card.cid.prod_name[0] = '0';
    card.ext_csd.rev = 7; check(&card, &mrq, -EPERM); card.ext_csd.rev = 8;
    card.ext_csd.data_sector_size = 4096; check(&card, &mrq, -EPERM); card.ext_csd.data_sector_size = 512;
    for (unsigned area = 1; area < 8; area++) {
        card.ext_csd.part_config = area; check(&card, &mrq, -EPERM);
    }
    card.ext_csd.part_config = 0;
    card.ext_csd.sectors--; check(&card, &mrq, -EPERM); card.ext_csd.sectors += 2;
    check(&card, &mrq, -EPERM); card.ext_csd.sectors--;
    check(NULL, &mrq, -EPERM);
    cmd.data = NULL; check(&card, &mrq, -EPERM); cmd.data = &data;
    mrq.data = NULL; check(&card, &mrq, -EPERM); cmd.data = NULL;
    cmd.opcode = MMC_STOP_TRANSMISSION; cmd.flags = stop_flags; check(&card, &mrq, 0);
    cmd.arg = 1; check(&card, &mrq, -EPERM); cmd.arg = 0;
    cmd.flags = MMC_RSP_R1B | MMC_CMD_AC; check(&card, &mrq, -EPERM);
    cmd.opcode = MMC_SWITCH; check(&card, &mrq, -EBADMSG);
    for (unsigned opcode = 0; opcode < 64; opcode++) {
        cmd.opcode = opcode;
        cmd.arg = opcode == 3 || opcode == 9 || opcode == 10 || opcode == 13 ? 0x10000 : 0;
        cmd.flags = stop_flags;
        int expected = hi3798mv100_ident_request(&mrq);
        if (opcode == MMC_STOP_TRANSMISSION) expected = 0;
        check(&card, &mrq, expected);
    }
    struct dw_mci host = {0};
    assert(mv100_ident_validate(&host, NULL) == -EPERM);
    struct mmc_request empty = {0};
    assert(mv100_ident_validate(&host, &empty) == -EPERM);
    assert(hi3798mv100_emmc_ro_request(NULL, true, 15269888) == -EPERM);
    struct dw_mci_slot slot = {.host = &host};
    struct mmc_host mmc = {.slot = &slot}; slot.mmc = &mmc; host.slot = &slot;
    cmd.opcode = MMC_READ_SINGLE_BLOCK; cmd.arg = 28672; cmd.flags = read_flags;
    cmd.data = mrq.data = &data;
    assert(mv100_ident_validate(&host, &mrq) == -EPERM);
    memset(&mmc, 0xff, sizeof(mmc)); mmc.slot = &slot;
    assert(mv100_ident_slot(&slot) == 0);
    assert(mmc.caps == MMC_CAP_NONREMOVABLE && mmc.caps2 == (MMC_CAP2_NO_SD | MMC_CAP2_NO_SDIO));
    assert(!mmc.pm_caps && mmc.f_max == 25000000 && !mmc.dsr_req);
    assert(mmc.max_blk_size == 512 && mmc.max_blk_count == 8);
    assert(mmc.max_req_size == 4096 && mmc.max_seg_size == 4096);
    /* Other drivers still reach their ordinary queue. */
    host.drv_data = NULL; queued = completed = presence_checked = 0;
    dw_mci_request(&mmc, &mrq);
    assert(queued == 1 && !completed && presence_checked == 1);
    puts("EMMC_RO_POLICY_QUEUE_PASS: actual validator/queue, all opcodes/directions/flags/sidecars, range and user-area/card guard; no writes reach hardware");
    puts("EMMC_RO_SLOT_PASS: actual final callback clears CMD23/high-speed/PM and bounds requests to eight sectors");
}
'''

BLOCK_HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#define IS_ENABLED(option) (option)
#define MMC_BLK_DATA_AREA_RPMB 4
#define CCC_BLOCK_READ 4
#define ENODEV 19
#define ENOMEM 12
#define WQ_MEM_RECLAIM 1
#define WQ_HIGHPRI 2
#define IS_ERR(value) false
#define PTR_ERR(value) (-1)
#define pr_err(...) ((void)0)
struct mmc_card {
    bool mmc, combo;
    unsigned nr_parts;
    struct { unsigned area_type, part_cfg, size, force_ro; const char *name; } part[3];
    struct { unsigned cmdclass; } csd;
    int dev; void *complete_wq;
};
struct mmc_blk_data { int unused; };
static unsigned allocations, rpmb_parts, rpmb_registrations, fixups, main_allocations;
#define mmc_card_mmc(card) ((card)->mmc)
#define mmc_card_sd_combo(card) ((card)->combo)
#define mmc_blk_fixups 0
static int mmc_blk_alloc_rpmb_part(struct mmc_card *c, struct mmc_blk_data *m, unsigned cfg,
                                  unsigned size, const char *name) {
    (void)c; (void)m; (void)cfg; (void)size; (void)name; rpmb_parts++; return 0;
}
static int mmc_blk_alloc_part(struct mmc_card *c, struct mmc_blk_data *m, unsigned cfg,
                            unsigned size, unsigned ro, const char *name, unsigned type) {
    (void)c; (void)m; (void)cfg; (void)size; (void)ro; (void)name; (void)type; allocations++; return 0;
}
static void mmc_fixup_device(struct mmc_card *c, int f) { (void)c; (void)f; fixups++; }
static void *alloc_workqueue(const char *name, unsigned flags, unsigned workers) {
    (void)name; (void)flags; (void)workers; return (void *)1;
}
static struct mmc_blk_data *mmc_blk_alloc(struct mmc_card *card) {
    (void)card; static struct mmc_blk_data md; main_allocations++; return &md;
}
#define mmc_blk_add_debugfs(c, md) ((void)(c), (void)(md))
#define pm_runtime_set_autosuspend_delay(d, ms) ((void)(d), (void)(ms))
#define pm_runtime_use_autosuspend(d) ((void)(d))
#define pm_runtime_set_active(d) ((void)(d))
#define pm_runtime_enable(d) ((void)(d))
static void mmc_blk_rpmb_add(struct mmc_card *c) { (void)c; rpmb_registrations++; }
#define mmc_blk_remove_parts(c, md) ((void)(c), (void)(md))
#define mmc_blk_remove_req(md) ((void)(md))
#define destroy_workqueue(wq) ((void)(wq))
/* PARTS */
/* PROBE */
int main(void) {
    struct mmc_card card = {.mmc = true, .nr_parts = 3, .csd = {.cmdclass = CCC_BLOCK_READ},
        .part = {{.size = 4194304}, {.size = 4194304}, {.size = 4194304, .area_type = MMC_BLK_DATA_AREA_RPMB}}};
    struct mmc_blk_data md = {0};
    assert(mmc_blk_alloc_parts(&card, &md) == 0);
    assert(allocations == (CONFIG_HI3798MV100_EMMC_READ_ONLY ? 0 : 2));
    assert(rpmb_parts == (CONFIG_HI3798MV100_EMMC_READ_ONLY ? 0 : 1));
    allocations = rpmb_parts = 0;
    assert(mmc_blk_probe(&card) == 0);
    assert(main_allocations == 1 && fixups == 1);
    assert(allocations == (CONFIG_HI3798MV100_EMMC_READ_ONLY ? 0 : 2));
    assert(rpmb_parts == (CONFIG_HI3798MV100_EMMC_READ_ONLY ? 0 : 1));
    assert(rpmb_registrations == !CONFIG_HI3798MV100_EMMC_READ_ONLY);
    printf("EMMC_RO_BLOCK_CORE_PASS: actual allocation/probe, RO=%d; user disk retained and both hardware-partition/RPMB paths suppressed only in explicit profile\n", CONFIG_HI3798MV100_EMMC_READ_ONLY);
}
'''

READONLY_HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#define IS_ENABLED(option) (option)
#define CCC_BLOCK_WRITE 16
#define EINVAL 22
struct mmc_card { bool readonly; struct { unsigned cmdclass; } csd; };
#define mmc_card_mmc(card) ((void)(card), true)
#define mmc_card_sd(card) ((void)(card), false)
#define mmc_card_readonly(card) ((card)->readonly)
struct gendisk { bool readonly; };
struct device { struct gendisk *disk; };
struct device_attribute { int unused; };
struct mmc_blk_data { bool read_only; };
static struct mmc_blk_data md;
#define dev_to_disk(dev) ((dev)->disk)
static struct mmc_blk_data *mmc_blk_get(struct gendisk *disk) { (void)disk; return &md; }
static void mmc_blk_put(struct mmc_blk_data *data) { assert(data == &md); }
static void set_disk_ro(struct gendisk *disk, bool ro) { disk->readonly = ro; }
static int kstrtoul(const char *buf, unsigned base, unsigned long *value) {
    (void)base;
    if (buf[1] || (buf[0] != '0' && buf[0] != '1')) return -1;
    *value = buf[0] - '0'; return 0;
}
/* READONLY */
/* FORCE_RO */
int main(void) {
    struct mmc_card card = {0};
    struct gendisk disk = {0};
    struct device dev = {.disk = &disk};
    for (unsigned protected = 0; protected < 2; protected++) {
        for (unsigned writable = 0; writable < 2; writable++) {
            card.readonly = protected;
            card.csd.cmdclass = writable ? CCC_BLOCK_WRITE : 0;
            md.read_only = mmc_blk_readonly(&card);
            bool expected = CONFIG_HI3798MV100_EMMC_READ_ONLY || protected || !writable;
            assert(md.read_only == expected);
            set_disk_ro(&disk, md.read_only);
            assert(disk.readonly == expected);
            assert(force_ro_store(&dev, NULL, "0", 1) == 1);
            assert(disk.readonly == expected);
            assert(force_ro_store(&dev, NULL, "1", 1) == 1);
            assert(disk.readonly);
            assert(force_ro_store(&dev, NULL, "bad", 3) == -EINVAL);
            assert(disk.readonly);
            assert(force_ro_store(&dev, NULL, "0", 1) == 1);
            assert(disk.readonly == expected);
        }
    }
    printf("EMMC_RO_DISK_FLAG_PASS actual MMC readonly and force_ro callback profile=%d; writable card metadata and flag-clear attempts covered\n", CONFIG_HI3798MV100_EMMC_READ_ONLY);
}
'''


def test(linuxsrc):
    driver_path = "drivers/mmc/host/dw_mmc-hi3798mv100-ident.c"
    driver = (linuxsrc / driver_path).read_text()
    assert driver == (ROOT / "overlay" / driver_path).read_text()
    assert '.force_ro = IS_ENABLED(CONFIG_HI3798MV100_EMMC_READ_ONLY)' in driver
    validate = driver[driver.index('static int mv100_ident_validate('):driver.index('static int mv100_ident_voltage(')]
    slot = driver[driver.index('static int mv100_ident_slot('):driver.index('static int mv100_ident_validate(')]
    dw = (linuxsrc / 'drivers/mmc/host/dw_mmc.c').read_text()
    request = dw[dw.index('static void dw_mci_request('):dw.index('static void dw_mci_set_ios(')]
    assert request.index('validate_request(host, mrq)') < request.index('dw_mci_get_cd(mmc)')
    block = (linuxsrc / 'drivers/mmc/core/block.c').read_text()
    parts = block[block.index('static int mmc_blk_alloc_parts('):block.index('static void mmc_blk_remove_req(')]
    probe = block[block.index('static int mmc_blk_probe('):block.index('static void mmc_blk_remove(')]
    host = (linuxsrc / 'include/linux/mmc/host.h').read_text()
    names = ('MMC_CAP_NONREMOVABLE', 'MMC_CAP2_NO_SD', 'MMC_CAP2_NO_SDIO')
    caps = '\n'.join(re.search(rf'^#define {name}\s+[^\n]+', host, re.MULTILINE)[0] for name in names)
    policy = HARNESS.replace('/* HOST_CAPS */', caps).replace('/* SLOT */', slot)
    policy = '#include "hi3798mv100-emmc-rw-policy.h"\n' + policy
    policy = policy.replace('/* VALIDATE */', validate).replace('/* QUEUE */', request)
    core = BLOCK_HARNESS.replace('/* PARTS */', parts).replace('/* PROBE */', probe)
    # OpenWrt inserts its DT-partition helper before alloc_req. Extract only
    # the actual readonly function so unrelated downstream helpers stay out.
    start = block.index('static inline int mmc_blk_readonly(')
    readonly = block[start:block.index('\n}\n', start) + 3]
    force_ro = block[block.index('static ssize_t force_ro_store('):block.index('static DEVICE_ATTR(force_ro,')]
    assert '\tmd->read_only = mmc_blk_readonly(card);\n' in block
    assert 'set_disk_ro(md->disk, md->read_only || default_ro);' in block
    flags = READONLY_HARNESS.replace('/* READONLY */', readonly).replace('/* FORCE_RO */', force_ro)
    with tempfile.TemporaryDirectory(prefix='emmc-ro-') as directory:
        temp = Path(directory)
        (temp / 'linux/mmc').mkdir(parents=True)
        (temp / 'asm-generic').mkdir()
        for name in ('core.h', 'mmc.h'):
            shutil.copyfile(linuxsrc / 'include/linux/mmc' / name, temp / 'linux/mmc' / name)
        shutil.copyfile(ROOT / 'overlay/include/linux/mmc/ty1208z-samples.h', temp / 'linux/mmc/ty1208z-samples.h')
        for name in ('errno.h', 'errno-base.h'):
            shutil.copyfile(linuxsrc / 'include/uapi/asm-generic' / name, temp / 'asm-generic' / name)
        (temp / 'linux/errno.h').write_text('#include <asm-generic/errno.h>\n')
        (temp / 'linux/types.h').write_text(
            '#include <stdint.h>\n#include <stddef.h>\n#include <stdbool.h>\n'
            'typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;\n'
            'typedef uint64_t u64; typedef int32_t s32;\n#define BIT(n) (1U << (n))\n')
        (temp / 'linux/completion.h').write_text('struct completion { int unused; };\n')
        for name, harness, enabled, samples in (
                ('policy', policy, 1, 0), ('policy-samples-enabled', policy, 1, 1),
                ('block-ro', core, 1, 0), ('block-ordinary', core, 0, 0),
                ('readonly-ro', flags, 1, 0), ('readonly-ordinary', flags, 0, 0)):
            path = temp / (name + '.c')
            path.write_text(harness)
            command = ['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                       '-fsanitize=address,undefined', '-fno-pie', '-no-pie', '-I', str(temp),
                       '-I', str(ROOT / 'overlay/drivers/mmc/host'),
                       f'-DCONFIG_HI3798MV100_EMMC_READ_ONLY={enabled}',
                       '-DCONFIG_HI3798MV100_EMMC_WRITE=0',
                       '-DCONFIG_HI3798MV100_SD_READ_ONLY=0',
                       '-DCONFIG_HI3798MV100_SD_WRITE=0']
            if samples:
                command.append('-DCONFIG_HI3798MV100_EMMC_READ_SAMPLES=1')
            if name.startswith('block-'):
                # Upstream uses an int index against unsigned nr_parts;
                # retain its real types and the kernel's warning policy.
                command.append('-Wno-sign-compare')
            if name.startswith('readonly-'):
                command.extend(('-include', 'sys/types.h', '-Wno-unused-parameter'))
            binary = temp / name
            subprocess.run([*command, str(path), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linuxsrc', type=Path, required=True)
    test(parser.parse_args().linuxsrc)
