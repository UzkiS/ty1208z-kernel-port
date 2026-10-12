/* SPDX-License-Identifier: MIT */
/* Bounded loopback NTP server for the isolated ARM QEMU test, never the board. */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopping;

static void stop_server(int number)
{
    (void)number;
    stopping = 1;
}

static bool isolated_guest(void)
{
    char compatible[256];
    FILE *file = fopen("/sys/firmware/devicetree/base/compatible", "rb");
    if (!file)
        return false;
    size_t length = fread(compatible, 1, sizeof(compatible), file);
    fclose(file);
    for (size_t offset = 0; offset < length;) {
        size_t size = strnlen(compatible + offset, length - offset);
        if (size == strlen("linux,dummy-virt") &&
            memcmp(compatible + offset, "linux,dummy-virt", size) == 0)
            return true;
        offset += size + 1;
    }
    return false;
}

static int64_t monotonic_ns(void)
{
    struct timespec current;
    if (clock_gettime(CLOCK_MONOTONIC, &current) != 0) {
        perror("clock_gettime");
        exit(1);
    }
    return (int64_t)current.tv_sec * INT64_C(1000000000) + current.tv_nsec;
}

static void put_u32(unsigned char *output, uint32_t value)
{
    value = htonl(value);
    memcpy(output, &value, sizeof(value));
}

static void put_timestamp(unsigned char *output, uint64_t epoch, int64_t elapsed)
{
    uint64_t seconds = epoch + (uint64_t)(elapsed / INT64_C(1000000000));
    uint64_t nanoseconds = (uint64_t)(elapsed % INT64_C(1000000000));
    /* NTP wire seconds wrap modulo 2^32 at the 2036 era boundary. */
    put_u32(output, (uint32_t)(seconds + UINT64_C(2208988800)));
    put_u32(output + 4, (uint32_t)((nanoseconds << 32) / UINT64_C(1000000000)));
}

int main(int argc, char **argv)
{
    if (!isolated_guest()) {
        fputs("NTP_FIXTURE_REFUSED: requires isolated QEMU virt\n", stderr);
        return 2;
    }
    if (argc != 2) {
        fputs("usage: ntp-qemu-fixture TEST_EPOCH\n", stderr);
        return 2;
    }
    char *end;
    errno = 0;
    uint64_t epoch = strtoull(argv[1], &end, 10);
    if (errno || *end || !*argv[1] ||
        (epoch != UINT64_C(2085978400) && epoch != UINT64_C(2085978596) &&
         epoch != UINT64_C(2147483768) && epoch != UINT64_C(2208988800))) {
        fputs("NTP_FIXTURE_REFUSED: epoch outside fixed test cases\n", stderr);
        return 2;
    }
    int server = socket(AF_INET, SOCK_DGRAM, 0);
    if (server < 0) {
        perror("socket");
        return 1;
    }
    struct sockaddr_in address = {
        .sin_family = AF_INET,
        .sin_port = htons(123),
        .sin_addr.s_addr = htonl(INADDR_LOOPBACK),
    };
    if (bind(server, (struct sockaddr *)&address, sizeof(address)) != 0) {
        perror("bind loopback:123");
        close(server);
        return 1;
    }
    struct sigaction action = {.sa_handler = stop_server};
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, NULL) != 0 || sigaction(SIGINT, &action, NULL) != 0) {
        perror("sigaction");
        close(server);
        return 1;
    }
    int64_t started = monotonic_ns();
    unsigned int responses = 0, rejected = 0;
    printf("NTP_FIXTURE_READY epoch=%" PRIu64 " era=%" PRIu64 " wire_seconds=%" PRIu32 "\n",
           epoch, (epoch + UINT64_C(2208988800)) >> 32,
           (uint32_t)(epoch + UINT64_C(2208988800)));
    fflush(stdout);
    while (!stopping && monotonic_ns() - started < INT64_C(40000000000) &&
           responses + rejected < 64) {
        struct pollfd event = {.fd = server, .events = POLLIN};
        int status = poll(&event, 1, 200);
        if (status < 0) {
            if (errno == EINTR)
                continue;
            perror("poll");
            close(server);
            return 1;
        }
        if (!status)
            continue;
        unsigned char request[512], reply[48] = {0};
        struct sockaddr_in peer;
        socklen_t peer_size = sizeof(peer);
        ssize_t received = recvfrom(server, request, sizeof(request), 0,
                                    (struct sockaddr *)&peer, &peer_size);
        if (received != 48 || peer.sin_family != AF_INET ||
            peer.sin_addr.s_addr != htonl(INADDR_LOOPBACK) ||
            (request[0] & 7U) != 3U || ((request[0] >> 3) & 7U) < 3U ||
            ((request[0] >> 3) & 7U) > 4U) {
            rejected++;
            continue;
        }
        /* RFC 5905 server mode, stratum 1, zero leap warning; echo origin. */
        reply[0] = (4U << 3) | 4U;
        reply[1] = 1;
        reply[2] = request[2];
        reply[3] = (unsigned char)-20;
        put_u32(reply + 8, 1); /* 1/65536 second root dispersion */
        memcpy(reply + 12, "LOCL", 4);
        put_timestamp(reply + 16, epoch - 1, 0);
        memcpy(reply + 24, request + 40, 8);
        put_timestamp(reply + 32, epoch, monotonic_ns() - started);
        put_timestamp(reply + 40, epoch, monotonic_ns() - started);
        if (sendto(server, reply, sizeof(reply), 0,
                   (struct sockaddr *)&peer, peer_size) != (ssize_t)sizeof(reply)) {
            perror("sendto");
            close(server);
            return 1;
        }
        responses++;
    }
    close(server);
    printf("NTP_FIXTURE_COMPLETE responses=%u rejected=%u\n", responses, rejected);
    /* The client owns sample selection; also require its observed clock step. */
    return responses > 0 && rejected == 0 ? 0 : 1;
}
