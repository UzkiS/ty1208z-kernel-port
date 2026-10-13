/* SPDX-License-Identifier: ISC */
/* Fixed read-only WID queries. No firmware, memory writes, reset or RF setup. */
#define _POSIX_C_SOURCE 200809L
#define _FILE_OFFSET_BITS 64
#define _TIME_BITS 64
#include <fcntl.h>
#include <linux/usbdevice_fs.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include "rda_usb_identity_protocol.h"

#define RDA_SYSFS "/sys/bus/usb/devices/1-2"

static int read_file(const char *path, uint8_t *data, size_t capacity)
{
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return -errno;
    size_t used = 0;
    while (used < capacity) {
        ssize_t size = read(fd, data + used, capacity - used);
        if (size < 0) {
            int error = errno;
            close(fd);
            return -error;
        }
        if (!size) {
            close(fd);
            return (int)used;
        }
        used += (size_t)size;
    }
    uint8_t extra;
    ssize_t size = read(fd, &extra, 1);
    close(fd);
    return size == 0 ? (int)used : -EMSGSIZE;
}

static int attribute(const char *name, const char *expected)
{
    char path[160];
    uint8_t data[64];
    snprintf(path, sizeof(path), RDA_SYSFS "/%s", name);
    int size = read_file(path, data, sizeof(data));
    return size == (int)strlen(expected) && !memcmp(data, expected, (size_t)size)
           ? 0 : -ENODEV;
}

static int device_number(const char *name)
{
    char path[160];
    uint8_t data[32] = {0};
    snprintf(path, sizeof(path), RDA_SYSFS "/%s", name);
    int size = read_file(path, data, sizeof(data) - 1);
    if (size < 2 || data[size - 1] != '\n')
        return -EINVAL;
    for (int i = 0; i < size - 1; i++)
        if (data[i] < '0' || data[i] > '9')
            return -EINVAL;
    char *end;
    long value = strtol((char *)data, &end, 10);
    return end == (char *)data + size - 1 && value > 0 && value < 256
           ? (int)value : -EINVAL;
}

static int checked_device(void)
{
    struct utsname name;
    uint8_t data[512];
    const char compatible[] = "tianyi,ty1208z-ca-usb-host-experiment\0hi3798mv100-series";
    if (uname(&name) || strcmp(name.release, "6.12.112-ty1208z-usb-host1"))
        return -ENODEV;
    int size = read_file("/sys/firmware/devicetree/base/compatible", data, sizeof(data));
    if (size != sizeof(compatible) || memcmp(data, compatible, sizeof(compatible)))
        return -ENODEV;
    if (attribute("idVendor", "1e04\n") || attribute("idProduct", "8888\n") ||
        attribute("bcdDevice", "0000\n") || attribute("speed", "480\n") ||
        attribute("bConfigurationValue", "1\n"))
        return -ENODEV;
    struct stat binding;
    if (!lstat("/sys/bus/usb/devices/1-2:1.0/driver", &binding) || errno != ENOENT)
        return -EBUSY;
    size = read_file(RDA_SYSFS "/descriptors", data, sizeof(data));
    if (size < 0 || rda_id_descriptors(data, (size_t)size))
        return -ENODEV;
    int bus = device_number("busnum"), device = device_number("devnum");
    if (bus != 1 || device < 1)
        return -ENODEV;
    char path[64];
    snprintf(path, sizeof(path), "/dev/bus/usb/%03d/%03d", bus, device);
    int fd = open(path, O_RDWR | O_CLOEXEC);
    if (fd < 0)
        return -errno;
    /* Re-read from the opened usbfs node before claiming/sending anything. */
    size = (int)read(fd, data, sizeof(data));
    if (size < 0 || rda_id_descriptors(data, (size_t)size)) {
        close(fd);
        return -ENODEV;
    }
    return fd;
}

static int64_t milliseconds(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now))
        return -1;
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static int query(int fd, uint16_t wid, uint8_t seq, uint8_t out[20])
{
    uint8_t request[8], response[512];
    int size = rda_id_query(wid, seq, request);
    if (size < 0)
        return size;
    struct usbdevfs_bulktransfer transfer = {
        .ep = 1, .len = sizeof(request), .timeout = 500, .data = request
    };
    int64_t started = milliseconds();
    if (started < 0)
        return -EIO;
    int actual = ioctl(fd, USBDEVFS_BULK, &transfer);
    if (actual < 0)
        return -errno;
    if (actual != (int)sizeof(request))
        return -EIO;
    for (unsigned int attempt = 0; attempt < 5; attempt++) {
        int64_t now = milliseconds();
        if (now < 0)
            return -EIO;
        int64_t remaining = started + 2000 - now;
        if (remaining <= 0)
            return -ETIMEDOUT;
        transfer = (struct usbdevfs_bulktransfer){
            .ep = 0x82, .len = sizeof(response), .timeout = (unsigned int)remaining,
            .data = response
        };
        actual = ioctl(fd, USBDEVFS_BULK, &transfer);
        if (actual < 0)
            return -errno;
        /* Bounded transport evidence for unsupported/pre-firmware replies.
         * This is separate from validated identity data; never parse a dump
         * as a successful query result. */
        printf("RDA_USB_IDENTITY_RX wid=%04x bytes=%d prefix=", wid, actual);
        for (int byte = 0; byte < actual && byte < 64; byte++)
            printf("%02x", response[byte]);
        printf(" truncated=%d\n", actual > 64);
        int result = rda_id_response(response, (size_t)actual, wid, seq, out);
        if (result != -EAGAIN)
            return result;
    }
    return -ETIMEDOUT;
}

static int selftest(void)
{
    uint8_t request[8], out[20];
    const uint8_t response[] = {13, 0x30, 'R', 7, 11, 0, 0x1e, 0x20, 4, 1, 2, 3, 4};
    if (rda_id_query(RDA_ID_STATE, 7, request) != 8 ||
        memcmp(request, (uint8_t[]){8, 0x40, 'Q', 7, 6, 0, 0x1e, 0x20}, 8) ||
        rda_id_query(0x201f, 7, request) != -EPERM ||
        rda_id_response(response, sizeof(response), RDA_ID_STATE, 7, out) != 4 ||
        memcmp(out, (uint8_t[]){1, 2, 3, 4}, 4))
        return 1;
    for (size_t i = 0; i < sizeof(response); i++)
        if (rda_id_response(response, i, RDA_ID_STATE, 7, out) >= 0)
            return 1;
    puts("RDA_USB_IDENTITY_SELFTEST_PASS wire-only no-device-access");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    if (argc != 2 || strcmp(argv[1], "--probe")) {
        fputs("Usage: rda-usb-identity --selftest | --probe\n", stderr);
        return 2;
    }
    int fd = checked_device();
    if (fd < 0) {
        printf("RDA_USB_IDENTITY_REFUSED error=%d no-query-sent\n", fd);
        return 1;
    }
    unsigned int interface = 0;
    if (ioctl(fd, USBDEVFS_CLAIMINTERFACE, &interface)) {
        printf("RDA_USB_IDENTITY_REFUSED claim-error=%d no-query-sent\n", errno);
        close(fd);
        return 1;
    }
    const uint16_t wids[] = {RDA_ID_STATE, RDA_ID_REVISION, RDA_ID_FIRMWARE};
    int failures = 0;
    for (size_t i = 0; i < sizeof(wids) / sizeof(wids[0]); i++) {
        uint8_t data[20] = {0};
        int size = query(fd, wids[i], (uint8_t)(0xa1 + i), data);
        printf("RDA_USB_IDENTITY_QUERY wid=%04x result=%d", wids[i], size);
        if (size > 0) {
            fputs(" data=", stdout);
            for (int byte = 0; byte < size; byte++)
                printf("%02x", data[byte]);
        } else {
            failures++;
        }
        putchar('\n');
    }
    int release = ioctl(fd, USBDEVFS_RELEASEINTERFACE, &interface);
    int release_error = release ? errno : 0;
    close(fd); /* Also drops the claim if explicit release failed. */
    printf("RDA_USB_IDENTITY_COMPLETE query-only failures=%d release-error=%d\n",
           failures, release_error);
    return failures || release_error ? 1 : 0;
}
