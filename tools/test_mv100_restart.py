#!/usr/bin/env python3
"""Execute the measured MV100 watchdog guard and reset writes with MMIO traps."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define __iomem
static u32 registers[1024], sysid;
static unsigned reads, writes;
static u32 readl(void *address)
{
    reads++;
    if (address == &sysid) { assert(!writes); return sysid; }
    unsigned offset = (u32 *)address - registers;
    assert(offset < 1024);
    if (writes) assert(writes == 4 && offset == 0xc00 / 4);
    else assert(offset == 0 || offset == 1 || offset == 2 || offset == 4 || offset == 5 ||
                offset == 0xc00 / 4 || (offset >= 0xfe0 / 4 && offset <= 0xffc / 4));
    return registers[offset];
}
static void writel(u32 value, void *address)
{
    const u32 offsets[] = {0xc00, 8, 0, 8}, values[] = {0x1acce551, 0, 0x100, 3};
    assert(reads == 15 && writes < 4);
    assert((u32 *)address - registers == offsets[writes] / 4 && value == values[writes]);
    registers[offsets[writes] / 4] = value;
    writes++;
}
#include "ty1208z-mv100-restart.h"
static void initialize(void)
{
    memset(registers, 0, sizeof(registers));
    registers[0] = registers[1] = 0xffffffff;
    sysid = 0x37980100;
    reads = writes = 0;
}
int main(void)
{
    const unsigned guarded[] = {0, 4, 8, 0x10, 0x14, 0xc00,
        0xfe0, 0xfe4, 0xfe8, 0xfec, 0xff0, 0xff4, 0xff8, 0xffc};
    for (unsigned bit = 0; bit < 32; bit++) {
        initialize(); sysid ^= 1U << bit;
        assert(!ty1208z_mv100_restart(registers, &sysid) && reads == 1 && !writes);
        for (unsigned i = 0; i < sizeof(guarded) / sizeof(guarded[0]); i++) {
            initialize(); registers[guarded[i] / 4] ^= 1U << bit;
            /* Only the low byte of each AMBA ID cell carries the identity. */
            bool ignored = guarded[i] >= 0xfe0 && bit >= 8;
            assert(ty1208z_mv100_restart(registers, &sysid) == ignored);
            assert(writes == (ignored ? 4U : 0U));
        }
    }
    initialize();
    assert(ty1208z_mv100_restart_ready(registers, &sysid) && reads == 15 && !writes);
    initialize();
    assert(ty1208z_mv100_restart(registers, &sysid) && reads == 16 && writes == 4);
    puts("MV100_RESTART_HELPER_PASS: measured SoC/inactive-register guard, mutation denial, exact reset-only writes");
}
'''


def test():
    with tempfile.TemporaryDirectory(prefix="mv100-restart-") as directory:
        path = Path(directory)
        (path / "linux").mkdir()
        for name in ("io.h", "types.h"):
            (path / "linux" / name).write_text("/* Harness supplies MMIO/types. */\n")
        program = path / "test.c"
        program.write_text(HARNESS)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", "-I", str(path),
                        "-I", str(ROOT / "overlay/drivers/power/reset"),
                        str(program), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    test()
