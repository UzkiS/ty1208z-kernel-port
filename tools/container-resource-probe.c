// SPDX-License-Identifier: GPL-2.0-only
/* Fixed bounded workloads for an isolated container; never run on the host. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

int main(int argc, char **argv)
{
    if (argc != 2)
        return 2;
    if (!strcmp(argv[1], "oom")) {
        const size_t bytes = 64U * 1024 * 1024;
        volatile unsigned char *area = malloc(bytes);
        if (!area)
            return 3;
        for (size_t i = 0; i < bytes; i += 4096)
            area[i] = (unsigned char)i;
        free((void *)area);
        fputs("CONTAINER_MEMORY_LIMIT_NOT_ENFORCED\n", stderr);
        return 4;
    }
    if (!strcmp(argv[1], "cpu")) {
        struct timespec start, now;
        volatile uint32_t value = 1;
        if (clock_gettime(CLOCK_MONOTONIC, &start))
            return 3;
        do {
            for (unsigned i = 0; i < 100000; i++)
                value = value * 1664525U + 1013904223U;
            if (clock_gettime(CLOCK_MONOTONIC, &now))
                return 3;
        } while ((int64_t)(now.tv_sec - start.tv_sec) * 1000000000 +
                 now.tv_nsec - start.tv_nsec < 2000000000);
        puts("CONTAINER_CPU_BUSY_PASS");
        return 0;
    }
    return 2;
}
