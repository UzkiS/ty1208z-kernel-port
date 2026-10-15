#!/usr/bin/env python3
"""Exercise real SD write validation and DW queue dispatch under sanitizers."""
import argparse
from pathlib import Path

from test_sd_ident import test as test_policy
from test_sd_ro import queue_harness

MAIN = r'''
int main(void)
{
    struct mmc_command cmd = {0}, side = {0};
    struct mmc_data data = {.blocks = 1, .blksz = 512};
    struct mmc_request mrq = {.cmd = &cmd, .data = &data};
    cmd.data = &data;
    const unsigned flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
    const unsigned read_stop = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC;
    const unsigned write_stop = MMC_RSP_SPI_R1B | MMC_RSP_R1B | MMC_CMD_AC;
    side.opcode = MMC_STOP_TRANSMISSION;
    cmd.flags = flags;
    for (unsigned opcode = 0; opcode < 64; opcode++) {
        cmd.opcode = opcode;
        for (unsigned direction = 1; direction <= 3; direction++) {
            data.flags = direction;
            for (unsigned blocks = 0; blocks <= 9; blocks++) {
                data.blocks = blocks;
                mrq.stop = data.stop = blocks > 1 ? &side : NULL;
                side.flags = direction == MMC_DATA_WRITE ? write_stop : read_stop;
                check(&mrq, blocks > 0 &&
                      ((direction == MMC_DATA_WRITE && opcode ==
                        (blocks == 1 ? MMC_WRITE_BLOCK : MMC_WRITE_MULTIPLE_BLOCK)) ||
                       (direction == MMC_DATA_READ && opcode ==
                        (blocks == 1 ? MMC_READ_SINGLE_BLOCK : MMC_READ_MULTIPLE_BLOCK))));
            }
        }
    }
    cmd.opcode = MMC_WRITE_BLOCK; data.flags = MMC_DATA_WRITE; data.blocks = 1;
    mrq.stop = data.stop = NULL;
    for (unsigned size = 0; size <= 1024; size++) {
        data.blksz = size; check(&mrq, size == 512);
    }
    data.blksz = 512;
    for (unsigned position = 0; position < 20; position++) {
        cmd.arg = position; check(&mrq, position < sectors);
    }
    cmd.arg = 0;
    for (unsigned bit = 0; bit < 32; bit++) {
        cmd.flags = flags ^ (1U << bit); check(&mrq, false);
    }
    cmd.flags = flags;
    mrq.sbc = &side; check(&mrq, false); mrq.sbc = NULL;
    mrq.stop = &side; check(&mrq, false); mrq.stop = NULL;
    data.stop = &side; check(&mrq, false); data.stop = NULL;
    cmd.data = NULL; check(&mrq, false); cmd.data = &data;
    card_missing = true; check(&mrq, false); card_missing = false;
    slot_missing = true; check(&mrq, false); slot_missing = false;
    addressed = false; check(&mrq, false); addressed = true;
    card_sd = false; check(&mrq, false); card_sd = true;
    card_read_bits = 10; check(&mrq, false); card_read_bits = 9;
    sectors = 0; check(&mrq, false);
    sectors = (1ULL << 32) + 1; check(&mrq, false);
    sectors = 1ULL << 32; cmd.arg = 0xffffffffU; check(&mrq, true);
    sectors = 16; cmd.arg = 16; check(&mrq, false); cmd.arg = 15; check(&mrq, true);
    data.flags = MMC_DATA_READ; cmd.opcode = MMC_READ_SINGLE_BLOCK; check(&mrq, true);
    sectors = 1000000; cmd.arg = 0;
    for (unsigned write = 0; write < 2; write++) {
        cmd.opcode = write ? MMC_WRITE_MULTIPLE_BLOCK : MMC_READ_MULTIPLE_BLOCK;
        data.flags = write ? MMC_DATA_WRITE : MMC_DATA_READ;
        side.flags = write ? write_stop : read_stop;
        mrq.stop = data.stop = &side;
        unsigned counts[] = {2, 8, 9, 512, 1024, 65535, 65536};
        for (unsigned i = 0; i < sizeof(counts)/sizeof(counts[0]); i++) {
            data.blocks = counts[i]; check(&mrq, counts[i] <= 65535);
        }
        data.blocks = 512; cmd.arg = sectors - 512; check(&mrq, true);
        cmd.arg++; check(&mrq, false); cmd.arg = 0;
        for (unsigned bit = 0; bit < 32; bit++) {
            side.arg = 1U << bit; check(&mrq, false); side.arg = 0;
            side.flags ^= 1U << bit; check(&mrq, false); side.flags ^= 1U << bit;
        }
        data.stop = NULL; check(&mrq, false); data.stop = &side;
        mrq.sbc = &side; check(&mrq, false); mrq.sbc = NULL;
    }
    mrq.stop = data.stop = NULL;
    cmd.data = mrq.data = NULL; cmd.opcode = MMC_SEND_STATUS;
    cmd.arg = 0x12340000; check(&mrq, true);
    cmd.opcode = MMC_ERASE; cmd.arg = 0; check(&mrq, false);
    struct mmc_request empty = {0};
    assert(hi3798mv100_sd_rw_request(&empty, true, 16) == -EPERM);
    puts("SD_RW_POLICY_QUEUE_PASS: CMD17/18/24/25, normal multi-block counts, end-of-card, STOP validation and forbidden commands");
}
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linuxsrc', type=Path, required=True)
    source = parser.parse_args().linuxsrc
    test_policy(source, queue_harness(source, MAIN, write=True))
