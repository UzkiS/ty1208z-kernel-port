// SPDX-License-Identifier: GPL-2.0-only
/* Fixed read observations only; never write, repair or submit mutating ioctls. */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <dirent.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/fs.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/sysmacros.h>
#include <unistd.h>

static uint32_t little32(const unsigned char *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static uint32_t big32(const unsigned char *p)
{
    return (uint32_t)p[3] | (uint32_t)p[2] << 8 |
           (uint32_t)p[1] << 16 | (uint32_t)p[0] << 24;
}

static uint32_t crc32(const unsigned char *p, size_t bytes)
{
    uint32_t crc = 0xffffffffU;
    for (size_t i = 0; i < bytes; i++) {
        crc ^= p[i];
        for (unsigned bit = 0; bit < 8; bit++)
            crc = crc >> 1 ^ (0xedb88320U & (0U - (crc & 1U)));
    }
    return crc ^ 0xffffffffU;
}

static int block_open(const char *path, unsigned minor_number, uint64_t expected)
{
    struct stat st;
    uint64_t bytes;
    int ro = 0, fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);

    if (fd >= 0 && !fstat(fd, &st) && S_ISBLK(st.st_mode) &&
        major(st.st_rdev) == 179 && minor(st.st_rdev) == minor_number &&
        !ioctl(fd, BLKROGET, &ro) && ro == 1 &&
        !ioctl(fd, BLKGETSIZE64, &bytes) && bytes == expected)
        return fd;
    if (fd >= 0)
        close(fd);
    fputs("EMMC_RO_PROBE_REFUSED device/readonly/capacity mismatch\n", stderr);
    return -1;
}

static int block_probe(void)
{
    unsigned char page[4096], overlap[1024], header[64];
    const uint64_t bytes = 7818182656ULL;
    int fd = block_open("/dev/mmcblk0", 0, bytes);
    if (fd < 0)
        return 1;
    if (pread(fd, page, sizeof(page), 0) != (ssize_t)sizeof(page) ||
        pread(fd, overlap, sizeof(overlap), 3584) != (ssize_t)sizeof(overlap) ||
        memcmp(page + 3584, overlap, 512) ||
        pread(fd, page, sizeof(page), (off_t)(bytes - sizeof(page))) != (ssize_t)sizeof(page) ||
        pread(fd, page, 512, (off_t)bytes) != 0) {
        close(fd);
        fputs("EMMC_RO_PROBE_FAILED page/overlap/end read\n", stderr);
        return 1;
    }
    close(fd);
    puts("EMMC_RO_BLOCK_READ_PASS bytes=7818182656 read_bytes=4096 ro=1");
    puts("EMMC_RO_OVERLAPPING_READ_PASS read_bytes=1024");
    puts("EMMC_RO_END_READ_PASS last_bytes=4096 eof=0");

    fd = block_open("/dev/mmcblk0p6", 6, 20ULL * 1024 * 1024);
    if (fd < 0)
        return 1;
    if (pread(fd, page, sizeof(page), 0) != (ssize_t)sizeof(page)) {
        close(fd);
        return 1;
    }
    close(fd);
    memcpy(header, page, sizeof(header));
    memset(header + 4, 0, 4);
    if (big32(page) != 0x27051956 || big32(page + 16) != 0x02000000 ||
        big32(page + 20) != 0x02000000 || crc32(header, sizeof(header)) != big32(page + 4) ||
        crc32(page, 512) != 0x2ba1a125) {
        fputs("EMMC_RO_PROBE_FAILED measured Hinas header\n", stderr);
        return 1;
    }
    puts("EMMC_RO_HINAS_HEADER_PASS crc32=2ba1a125 load=02000000 entry=02000000");

    fd = block_open("/dev/mmcblk0p9", 9, 6846ULL * 1024 * 1024);
    if (fd < 0)
        return 1;
    if (pread(fd, page, sizeof(page), 0) != (ssize_t)sizeof(page)) {
        close(fd);
        return 1;
    }
    close(fd);
    if (page[1080] != 0x53 || page[1081] != 0xef || little32(page + 1048) != 2) {
        fputs("EMMC_RO_PROBE_FAILED measured ext4 superblock\n", stderr);
        return 1;
    }
    puts("EMMC_RO_EXT4_SUPERBLOCK_PASS magic=ef53 block_size=4096");
    return 0;
}

/* Bounded symlink-free read; never print file names or contents. */
static int read_one_file(int parent, unsigned depth, unsigned *visited)
{
    int copy = dup(parent);
    DIR *directory;
    struct dirent *entry;
    int result = 0;
    if (copy < 0)
        return -1;
    directory = fdopendir(copy);
    if (!directory) {
        close(copy);
        return -1;
    }
    while (*visited < 1024 && (entry = readdir(directory))) {
        struct stat st;
        int fd;
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
            continue;
        (*visited)++;
        if (fstatat(parent, entry->d_name, &st, AT_SYMLINK_NOFOLLOW)) {
            result = -1;
            break;
        }
        if (S_ISREG(st.st_mode) && st.st_size > 0) {
            unsigned char buffer[4096];
            fd = openat(parent, entry->d_name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
            if (fd < 0) { result = -1; break; }
            ssize_t count = pread(fd, buffer, sizeof(buffer), 0);
            close(fd);
            if (count <= 0) { result = -1; break; }
            printf("EMMC_RO_FS_FILE_READ_PASS bytes=%zd content-and-name-excluded\n", count);
            result = 1;
            break;
        }
        if (S_ISDIR(st.st_mode) && depth < 8) {
            fd = openat(parent, entry->d_name, O_RDONLY | O_CLOEXEC | O_DIRECTORY | O_NOFOLLOW);
            if (fd < 0) { result = -1; break; }
            result = read_one_file(fd, depth + 1, visited);
            close(fd);
            if (result)
                break;
        }
    }
    closedir(directory);
    return result;
}

static int mounted_probe(const char *path)
{
    struct stat st;
    struct statvfs fs;
    unsigned visited = 0;
    if (strcmp(path, "/tmp/emmc-ro-mount"))
        return 2;
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_DIRECTORY | O_NOFOLLOW);
    if (fd < 0 || fstat(fd, &st) || major(st.st_dev) != 179 || minor(st.st_dev) != 9 ||
        fstatvfs(fd, &fs) || !(fs.f_flag & ST_RDONLY)) {
        if (fd >= 0)
            close(fd);
        fputs("EMMC_RO_FS_PROBE_REFUSED expected read-only p9\n", stderr);
        return 1;
    }
    puts("EMMC_RO_FS_MOUNT_PASS ro=1 partition=9");
    int result = read_one_file(fd, 0, &visited);
    close(fd);
    if (!result)
        puts("EMMC_RO_FS_NO_NONEMPTY_FILE bounded-search");
    return result == 1 ? 0 : 1;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--blocks"))
        return block_probe();
    if (argc == 3 && !strcmp(argv[1], "--mounted"))
        return mounted_probe(argv[2]);
    fputs("usage: emmc-ro-probe --blocks | --mounted /tmp/emmc-ro-mount\n", stderr);
    return 2;
}
