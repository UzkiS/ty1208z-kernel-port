#!/usr/bin/env python3
"""Execute the real userspace probe against fake RO blocks and bounded files."""
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/fs.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#include "fixture.h"
static int mode, short_read, reads, real_reads, opened, closed, duplicate;
static const char *fixture_root;
static int mock_open(const char *name, int flags, ...) {
    assert((flags & O_ACCMODE) == O_RDONLY && (flags & O_NOFOLLOW) && !(flags & O_CREAT));
    if (mode == 12) return -1;
    if (!strcmp(name, "/tmp/emmc-ro-mount")) {
        assert(flags & O_DIRECTORY); return open(fixture_root, flags);
    }
    int fd = !strcmp(name, "/dev/mmcblk0") ? 100 : !strcmp(name, "/dev/mmcblk0p6") ? 106 :
             !strcmp(name, "/dev/mmcblk0p9") ? 109 : -1;
    assert(fd >= 100); opened++; return fd;
}
static int mock_close(int fd) {
    if (fd < 100) return close(fd);
    assert(fd == 100 || fd == 106 || fd == 109); closed++; return 0;
}
static int mock_fstat(int fd, struct stat *st) {
    if (mode == 11) return -1;
    if (fd < 100) {
        int ret = fstat(fd, st); st->st_dev = makedev(mode == 14 ? 8 : 179, 9); return ret;
    }
    memset(st, 0, sizeof(*st)); st->st_mode = S_IFBLK;
    st->st_rdev = makedev(mode == 3 ? 8 : 179, mode == 4 ? 1 : fd - 100); return 0;
}
static int mock_fstatvfs(int fd, struct statvfs *st) {
    if (mode == 18) return -1;
    int ret = fstatvfs(fd, st); st->f_flag = mode == 13 ? 0 : ST_RDONLY; return ret;
}
static int mock_dup(int fd) { return mode == 16 ? -1 : (duplicate = dup(fd)); }
static DIR *mock_fdopendir(int fd) { return mode == 17 ? NULL : fdopendir(fd); }
static int mock_ioctl(int fd, unsigned long operation, ...) {
    assert(fd >= 100); va_list args; va_start(args, operation); void *output = va_arg(args, void *); va_end(args);
    if (mode == 5) return -1;
    if (operation == BLKROGET) { *(int *)output = mode == 1 ? 0 : 1; return 0; }
    assert(operation == BLKGETSIZE64);
    *(uint64_t *)output = fd == 100 ? 7818182656ULL : fd == 106 ? 20ULL * 1024 * 1024 : 6846ULL * 1024 * 1024;
    if (mode == 2) (*(uint64_t *)output)--;
    return 0;
}
static ssize_t mock_pread(int fd, void *out, size_t bytes, off_t offset) {
    assert(bytes <= 4096 && offset >= 0);
    if (fd < 100) { real_reads++; return mode == 15 ? 0 : pread(fd, out, bytes, offset); }
    reads++;
    if (reads == short_read) return (ssize_t)bytes - 1;
    unsigned char *p = out;
    if (fd == 100) {
        if ((uint64_t)offset == 7818182656ULL) return mode == 8 ? (ssize_t)bytes : 0;
        assert(!offset || offset == 3584 || (uint64_t)offset == 7818182656ULL - 4096);
        for (size_t i = 0; i < bytes; i++) p[i] = (unsigned char)(offset + (off_t)i);
        if (mode == 6 && offset == 3584) p[0] ^= 1;
    } else if (fd == 106) {
        assert(!offset && bytes == 4096); memset(out, 0, bytes); memcpy(out, header_seed, sizeof(header_seed));
        if (mode == 7) p[20] ^= 1;
    } else {
        assert(fd == 109 && !offset && bytes == 4096); memset(out, 0, bytes);
        p[1080] = mode == 9 ? 0 : 0x53; p[1081] = 0xef; p[1048] = mode == 10 ? 3 : 2;
    }
    return (ssize_t)bytes;
}
#define open mock_open
#define close mock_close
#define fstat mock_fstat
#define fstatvfs mock_fstatvfs
#define ioctl mock_ioctl
#define pread mock_pread
#define dup mock_dup
#define fdopendir mock_fdopendir
#define main emmc_ro_probe_main
/* ACTUAL */
#undef open
#undef close
#undef fstat
#undef fstatvfs
#undef ioctl
#undef pread
#undef dup
#undef fdopendir
#undef main
static void reset(int failure, int short_at) {
    mode = failure; short_read = short_at; reads = real_reads = opened = closed = 0;
}
int main(int argc, char **argv) {
    assert(argc == 2); fixture_root = argv[1];
    char *blocks[] = {"emmc-ro-probe", "--blocks", NULL};
    reset(0, 0); assert(emmc_ro_probe_main(2, blocks) == 0 && reads == 6 && opened == 3 && opened == closed);
    for (int i = 1; i <= 12; i++) {
        reset(i, 0); assert(emmc_ro_probe_main(2, blocks) != 0 && opened == closed);
    }
    for (int i = 1; i <= 6; i++) {
        reset(0, i); assert(emmc_ro_probe_main(2, blocks) != 0 && opened == closed);
    }
    char *mounted[] = {"emmc-ro-probe", "--mounted", "/tmp/emmc-ro-mount", NULL};
    reset(0, 0); assert(emmc_ro_probe_main(3, mounted) == 0 && real_reads == 1 && !opened);
    for (int i = 13; i <= 18; i++) {
        reset(i, 0); assert(emmc_ro_probe_main(3, mounted) != 0 && !opened);
        if (i == 17) assert(duplicate >= 0 && fcntl(duplicate, F_GETFD) == -1);
    }
    mounted[2] = "/tmp/emmc-ro-mount/../outside";
    reset(0, 0); assert(emmc_ro_probe_main(3, mounted) == 2 && !opened && !real_reads);
    reset(0, 0); assert(emmc_ro_probe_main(1, blocks) == 2 && !opened && !reads);
    puts("EMMC_RO_USER_PROBE_PASS actual read-only calls, exact major/minor/capacity, page/overlap/end/header/ext4 and bounded symlink-free file reads; every error refused and descriptors closed");
}
'''


def header_fixture():
    # Synthetic ordinary header. Match the measured sector CRC without
    # copying the user's firmware; a 32-bit linear CRC patch changes only
    # four padding bytes outside its 64-byte header.
    blob = bytearray(512)
    struct.pack_into('>I', blob, 0, 0x27051956)
    struct.pack_into('>III', blob, 12, 4096, 0x02000000, 0x02000000)
    blob[28:32] = bytes((5, 2, 2, 0))
    struct.pack_into('>I', blob, 4, zlib.crc32(blob[:64]))
    original = zlib.crc32(blob)
    basis = [None] * 32
    for bit in range(32):
        candidate = bytearray(blob)
        candidate[508 + bit // 8] ^= 1 << (bit % 8)
        value, mask = zlib.crc32(candidate) ^ original, 1 << bit
        for pivot in range(31, -1, -1):
            if value & (1 << pivot):
                if basis[pivot] is None:
                    basis[pivot] = (value, mask)
                    break
                value ^= basis[pivot][0]
                mask ^= basis[pivot][1]
    value, mask = original ^ 0x2ba1a125, 0
    for pivot in range(31, -1, -1):
        if value & (1 << pivot):
            assert basis[pivot] is not None
            value ^= basis[pivot][0]
            mask ^= basis[pivot][1]
    assert value == 0
    for bit in range(32):
        if mask & (1 << bit):
            blob[508 + bit // 8] ^= 1 << (bit % 8)
    assert zlib.crc32(blob) == 0x2ba1a125
    return blob


def test():
    source = (ROOT / 'tools/emmc-ro-probe.c').read_text()
    with tempfile.TemporaryDirectory(prefix='emmc-ro-user-probe-') as directory:
        path = Path(directory)
        tree = path / 'tree'
        tree.mkdir()
        (tree / 'link').symlink_to(path / 'outside')
        (path / 'outside').write_bytes(b'outside-must-not-be-read')
        (tree / 'file').write_bytes(b'nonempty-synthetic-content')
        seed = ','.join(str(value) for value in header_fixture())
        (path / 'fixture.h').write_text('static const unsigned char header_seed[512] = {' + seed + '};\n')
        (path / 'test.c').write_text(HARNESS.replace('/* ACTUAL */', source))
        binary = path / 'test'
        subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie', str(path / 'test.c'),
                        '-o', str(binary)], check=True)
        result = subprocess.run([str(binary), str(tree)], capture_output=True, text=True, check=True)
        assert 'EMMC_RO_USER_PROBE_PASS' in result.stdout
        assert 'nonempty-synthetic-content' not in result.stdout and 'outside-must-not-be-read' not in result.stdout
        print(result.stdout.splitlines()[-1])


if __name__ == '__main__':
    test()
