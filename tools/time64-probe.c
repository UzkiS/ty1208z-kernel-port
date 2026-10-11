/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#define _TIME_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static void fail(const char *operation)
{
    perror(operation);
    exit(1);
}

int main(int argc, char **argv)
{
    const time_t future = (time_t)2208988800LL; /* 2040-01-01 00:00:00 UTC */
    char path[] = "/tmp/time64-probe-XXXXXX";
    struct timespec wall, start, end, wait = { .tv_nsec = 50000000 };
    struct timespec stamps[2] = {{ .tv_sec = future }, { .tv_sec = future }};
    struct stat st;
    struct tm decoded;
    char iso[64];
    int fd;

    if (sizeof(time_t) != 8 || sizeof(st.st_mtim.tv_sec) != 8) {
        fprintf(stderr, "TIME64_FAIL: incompatible libc ABI\n");
        return 1;
    }
    if (argc > 1) {
        if (argc != 2 || strcmp(argv[1], "--set-clock-2040")) {
            fprintf(stderr, "usage: time64-probe [--set-clock-2040]\n");
            return 2;
        }
        /* Invoked automatically only inside isolated QEMU virt. */
        struct timespec target = { .tv_sec = future };
        if (clock_settime(CLOCK_REALTIME, &target)) fail("clock_settime(2040)");
    }
    if (clock_gettime(CLOCK_REALTIME, &wall)) fail("clock_gettime realtime");
    if (argc > 1 && (wall.tv_sec < future || wall.tv_sec > future + 10)) {
        fprintf(stderr, "TIME64_FAIL: future wall clock readback\n");
        return 1;
    }
    if (clock_gettime(CLOCK_MONOTONIC, &start)) fail("clock_gettime monotonic");
    while (nanosleep(&wait, &wait)) {
        if (errno != EINTR) fail("nanosleep");
    }
    if (clock_gettime(CLOCK_MONOTONIC, &end)) fail("clock_gettime monotonic end");
    int64_t elapsed = (int64_t)(end.tv_sec - start.tv_sec) * 1000000000 +
                      end.tv_nsec - start.tv_nsec;
    if (elapsed < 50000000 || elapsed > 10000000000LL) {
        fprintf(stderr, "TIME64_FAIL: monotonic interval=%" PRId64 "ns\n", elapsed);
        return 1;
    }
    if (!gmtime_r(&future, &decoded) ||
        !strftime(iso, sizeof(iso), "%Y-%m-%dT%H:%M:%SZ", &decoded))
        fail("gmtime_r/strftime");
    if (strcmp(iso, "2040-01-01T00:00:00Z")) {
        fprintf(stderr, "TIME64_FAIL: conversion=%s\n", iso);
        return 1;
    }
    fd = mkstemp(path);
    if (fd < 0) fail("open RAM test file");
    if (write(fd, "time64\n", 7) != 7) fail("write RAM test file");
    if (close(fd)) fail("close RAM test file");
    if (utimensat(AT_FDCWD, path, stamps, 0)) fail("utimensat(2040)");
    if (stat(path, &st)) fail("stat(2040)");
    if (st.st_mtim.tv_sec != future || st.st_atim.tv_sec != future) {
        fprintf(stderr, "TIME64_FAIL: file timestamp truncated\n");
        return 1;
    }
    if (unlink(path)) fail("unlink RAM test file");
    printf("TIME64_PASS sizeof(time_t)=%zu realtime=%" PRId64
           " file=%" PRId64 " converted=%s monotonic_ns=%" PRId64 "\n",
           sizeof(time_t), (int64_t)wall.tv_sec, (int64_t)st.st_mtim.tv_sec,
           iso, elapsed);
    return 0;
}
