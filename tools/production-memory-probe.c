// SPDX-License-Identifier: GPL-2.0-only
/* Writes only a new fixed file in a dedicated /tmp tmpfs. Never reads devices. */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <inttypes.h>
#include <linux/magic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <unistd.h>
#include <sched.h>
#include <sys/wait.h>
#include <stdlib.h>

#define TEST_BYTES (512U * 1024U * 1024U)
#define PAGE_BYTES 4096U
#define TEST_DIRECTORY "/tmp/production-memory-area"
#define TEST_FILE "memory-test"

static uint32_t pattern(uint32_t word, unsigned pass)
{
    uint32_t value = word * 0x9e3779b1U + 0x6a09e667U;
    return pass ? ~value : value;
}

static int check_entry(uint64_t entry, uint64_t *minimum, uint64_t *maximum, uint64_t *high)
{
    uint64_t pfn = entry & ((1ULL << 55) - 1);
    if (!(entry & (1ULL << 63)) || entry & (1ULL << 62) ||
        pfn < 0x01000000 / PAGE_BYTES || pfn >= 0x40000000 / PAGE_BYTES)
        return -1;
    if (pfn < *minimum)
        *minimum = pfn;
    if (pfn > *maximum)
        *maximum = pfn;
    if (pfn >= 0x30000000 / PAGE_BYTES)
        (*high)++;
    return 0;
}

int main(void)
{
    struct statfs fs;
    struct stat st;
    uint32_t *mapping = MAP_FAILED;
    uint64_t minimum = UINT64_MAX, maximum = 0, high = 0;
    unsigned long total_kib = 0, available_kib = 0;
    int directory = -1, fd = -1, pagemap = -1, status = 1;
    FILE *memory;
    char line[128];

    if (sysconf(_SC_PAGESIZE) != PAGE_BYTES || getuid() != 0)
        goto out;
    memory = fopen("/proc/meminfo", "r");
    if (!memory)
        goto out;
    while (fgets(line, sizeof(line), memory)) {
        unsigned long value;
        if (sscanf(line, "MemTotal: %lu kB", &value) == 1)
            total_kib = value;
        if (sscanf(line, "MemAvailable: %lu kB", &value) == 1)
            available_kib = value;
    }
    fclose(memory);
    if (total_kib < 900U * 1024U || total_kib > 1024U * 1024U ||
        available_kib < 560U * 1024U) {
        fputs("PRODUCTION_MEMORY_REFUSED insufficient-available-RAM\n", stderr);
        goto out;
    }
    directory = open(TEST_DIRECTORY, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (directory < 0 || fstatfs(directory, &fs) || fs.f_type != TMPFS_MAGIC)
        goto out;
    fd = openat(directory, TEST_FILE, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0 || fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size ||
        fstatfs(fd, &fs) || fs.f_type != TMPFS_MAGIC || ftruncate(fd, TEST_BYTES))
        goto out;
    mapping = mmap(NULL, TEST_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mapping == MAP_FAILED)
        goto out;
    for (unsigned pass = 0; pass < 2; pass++) {
        volatile uint32_t *words = mapping;
        pid_t children[4];
        for (unsigned cpu = 0; cpu < 4; cpu++) {
            children[cpu] = fork();
            if (children[cpu] < 0) exit(1);
            if (!children[cpu]) {
                cpu_set_t mask;
                CPU_ZERO(&mask); CPU_SET(cpu, &mask);
                if (sched_setaffinity(0, sizeof(mask), &mask)) _exit(2);
                uint32_t start = cpu * (TEST_BYTES / 4 / sizeof(*words));
                uint32_t end = (cpu + 1) * (TEST_BYTES / 4 / sizeof(*words));
                for (uint32_t word = start; word < end; word++) words[word] = pattern(word, pass);
                for (uint32_t word = start; word < end; word++)
                    if (words[word] != pattern(word, pass)) _exit(3);
                if (sched_getcpu() != (int)cpu) _exit(4);
                printf("PRODUCTION_CPU_PATTERN_PASS cpu=%u pass=%u bytes=%u\n", cpu, pass, TEST_BYTES / 4);
                fflush(stdout);
                _exit(0);
            }
        }
        for (unsigned cpu = 0; cpu < 4; cpu++) {
            int result;
            if (waitpid(children[cpu], &result, 0) != children[cpu] || !WIFEXITED(result) || WEXITSTATUS(result)) goto out;
        }
        for (uint32_t word = 0; word < TEST_BYTES / sizeof(*words); word++)
            if (words[word] != pattern(word, pass)) goto out;
        printf("PRODUCTION_PATTERN_PASS pass=%u bytes=%u\n", pass, TEST_BYTES);
        fflush(stdout);
    }
    pagemap = open("/proc/self/pagemap", O_RDONLY | O_CLOEXEC);
    if (pagemap < 0) {
        perror("PRODUCTION_PAGEMAP_OPEN_FAILED");
        goto out;
    }
    for (size_t page = 0; page < TEST_BYTES / PAGE_BYTES; page += 512) {
        uint64_t entries[512];
        off_t offset = ((uint64_t)(uintptr_t)mapping / PAGE_BYTES + page) * 8;
        ssize_t count = pread(pagemap, entries, sizeof(entries), offset);
        if (count != (ssize_t)sizeof(entries)) {
            fprintf(stderr, "PRODUCTION_PAGEMAP_READ_FAILED page=%zu count=%zd\n", page, count);
            goto out;
        }
        for (unsigned i = 0; i < 512; i++) {
            if (check_entry(entries[i], &minimum, &maximum, &high)) {
                fprintf(stderr, "PRODUCTION_PAGEMAP_ENTRY_REFUSED page=%zu present=%u swapped=%u pfn=%" PRIu64 "\n",
                        page + i, (unsigned)(entries[i] >> 63), (unsigned)((entries[i] >> 62) & 1),
                        (uint64_t)(entries[i] & ((1ULL << 55) - 1)));
                goto out;
            }
        }
    }
    if (high < 32768)
        goto out;
    status = 0;
out:
    if (pagemap >= 0)
        close(pagemap);
    if (mapping != MAP_FAILED)
        munmap(mapping, TEST_BYTES);
    if (fd >= 0) {
        close(fd);
        if (unlinkat(directory, TEST_FILE, 0))
            status = 1;
    }
    if (directory >= 0)
        close(directory);
    if (!status)
        printf("PRODUCTION_MEMORY_PASS bytes=%u high_pages=%" PRIu64 " pfn_min=%" PRIu64
               " pfn_max=%" PRIu64 " memtotal_kib=%lu file-removed\n",
               TEST_BYTES, high, minimum, maximum, total_kib);
    else
        fputs("PRODUCTION_MEMORY_FAILED bounded-tmpfs-test\n", stderr);
    return status;
}
