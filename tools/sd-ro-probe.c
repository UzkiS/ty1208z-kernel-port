// SPDX-License-Identifier: GPL-2.0-only
/* Fixed read-only observations. Never submit a write or mutating ioctl. */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/fs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
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

static int valid_device(const char *name)
{
    char *end;
    long partition;

    if (!strcmp(name, "/dev/mmcblk0"))
        return 1;
    if (strncmp(name, "/dev/mmcblk0p", 13))
        return 0;
    partition = strtol(name + 13, &end, 10);
    return *end == '\0' && partition > 0 && partition < 16;
}

/* Bounded, symlink-free read search. User filenames/content are never logged. */
static int read_one_file(int parent, unsigned depth, unsigned *visited)
{
    DIR *directory = fdopendir(dup(parent));
    struct dirent *entry;
    int result = 0;

    if (!directory)
        return -1;
    while (*visited < 1024 && (entry = readdir(directory))) {
        struct stat st;
        int child;

        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
            continue;
        (*visited)++;
        if (fstatat(parent, entry->d_name, &st, AT_SYMLINK_NOFOLLOW)) {
            result = -1;
            break;
        }
        if (S_ISREG(st.st_mode) && st.st_size > 0) {
            unsigned char buffer[4096];
            ssize_t count;

            child = openat(parent, entry->d_name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
            if (child < 0) {
                result = -1;
                break;
            }
            count = pread(child, buffer, sizeof(buffer), 0);
            close(child);
            if (count <= 0) {
                result = -1;
                break;
            }
            printf("SD_RO_FS_FILE_READ_PASS bytes=%zd content-and-name-excluded\n", count);
            result = 1;
            break;
        }
        if (S_ISDIR(st.st_mode) && depth < 8) {
            child = openat(parent, entry->d_name, O_RDONLY | O_CLOEXEC | O_DIRECTORY | O_NOFOLLOW);
            if (child < 0) {
                result = -1;
                break;
            }
            result = read_one_file(child, depth + 1, visited);
            close(child);
            if (result)
                break;
        }
    }
    closedir(directory);
    return result;
}

static int mounted_probe(const char *path)
{
    struct statvfs fs;
    unsigned visited = 0;
    int fd, result;
    struct stat st;
    const char *suffix;

    if (strncmp(path, "/tmp/sd-ro-mount-", strlen("/tmp/sd-ro-mount-")))
        return 2;
    suffix = path + strlen("/tmp/sd-ro-mount-");
    if (strncmp(suffix, "mmcblk0", 7) || strchr(suffix, '/') || strstr(suffix, ".."))
        return 2;
    fd = open(path, O_RDONLY | O_CLOEXEC | O_DIRECTORY | O_NOFOLLOW);
    if (fd < 0 || fstat(fd, &st) || major(st.st_dev) != 179 ||
        minor(st.st_dev) >= 16 || fstatvfs(fd, &fs) || !(fs.f_flag & ST_RDONLY)) {
        if (fd >= 0)
            close(fd);
        fputs("SD_RO_FS_PROBE_REFUSED non-read-only mount\n", stderr);
        return 1;
    }
    printf("SD_RO_FS_MOUNT_PASS ro=1 block_size=%lu blocks=%" PRIu64 "\n", fs.f_frsize, (uint64_t)fs.f_blocks);
    result = read_one_file(fd, 0, &visited);
    close(fd);
    if (!result)
        puts("SD_RO_FS_NO_NONEMPTY_FILE bounded-search");
    return result < 0 ? 1 : 0;
}

int main(int argc, char **argv)
{
    unsigned char page[4096];
    struct stat st;
    uint64_t bytes = 0;
    int ro = 0, fd;
    const char *device;
    int fs_mode = argc == 3 && !strcmp(argv[1], "--filesystem");

    if (argc == 3 && !strcmp(argv[1], "--mounted"))
        return mounted_probe(argv[2]);
    device = fs_mode ? argv[2] : argc == 2 ? argv[1] : "";
    if (!valid_device(device) || (!fs_mode && strcmp(device, "/dev/mmcblk0"))) {
        fputs("usage: sd-ro-probe /dev/mmcblk0 | --filesystem /dev/mmcblk0[pN] | --mounted /tmp/sd-ro-mount-mmcblk0[pN]\n", stderr);
        return 2;
    }
    fd = open(device, O_RDONLY | O_CLOEXEC);
    if (fd < 0 || fstat(fd, &st) || !S_ISBLK(st.st_mode) ||
        major(st.st_rdev) != 179 || minor(st.st_rdev) >= 16 ||
        ioctl(fd, BLKROGET, &ro) || ro != 1 ||
        ioctl(fd, BLKGETSIZE64, &bytes) || bytes < sizeof(page) + 512 ||
        bytes % 512 || bytes > (1ULL << 41)) {
        fprintf(stderr, "SD_RO_PROBE_REFUSED expected read-only block: %s\n", strerror(errno));
        if (fd >= 0)
            close(fd);
        return 1;
    }
    if (pread(fd, page, sizeof(page), 0) != (ssize_t)sizeof(page)) {
        fputs("SD_RO_PROBE_FAILED first-page read\n", stderr);
        close(fd);
        return 1;
    }
    if (fs_mode) {
        const char *type = "unknown";

        if (page[1080] == 0x53 && page[1081] == 0xef)
            type = "ext4";
        else if (!memcmp(page + 3, "EXFAT   ", 8))
            type = "exfat";
        else if (!memcmp(page + 54, "FAT12   ", 8) ||
                 !memcmp(page + 54, "FAT16   ", 8) ||
                 !memcmp(page + 82, "FAT32   ", 8))
            type = "vfat";
        puts(type);
        close(fd);
        return 0;
    }
    printf("SD_RO_BLOCK_READ_PASS bytes=%" PRIu64 " read_bytes=%zu ro=1\n", bytes, sizeof(page));
    printf("SD_RO_MBR signature=%s\n", page[510] == 0x55 && page[511] == 0xaa ? "55aa" : "absent");
    for (unsigned i = 0; i < 4; i++) {
        const unsigned char *entry = page + 446 + 16 * i;
        uint32_t start = little32(entry + 8), sectors = little32(entry + 12);

        if (entry[4] && sectors && start && (uint64_t)start + sectors <= bytes / 512)
            printf("SD_RO_MBR_PART index=%u type=%02x start=%" PRIu32 " sectors=%" PRIu32 "\n",
                   i + 1, entry[4], start, sectors);
    }
    /* A second read crosses the block layer's page boundary. No contents,
     * labels, card serials or user filenames are printed.
     */
    unsigned char overlap[1024];
    if (pread(fd, overlap, sizeof(overlap), 3584) != (ssize_t)sizeof(overlap) ||
        memcmp(page + 3584, overlap, 512)) {
        fputs("SD_RO_PROBE_FAILED overlapping read\n", stderr);
        close(fd);
        return 1;
    }
    puts("SD_RO_OVERLAPPING_READ_PASS read_bytes=1024");
    close(fd);
    return 0;
}
