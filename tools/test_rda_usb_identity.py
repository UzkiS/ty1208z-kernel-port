#!/usr/bin/env python3
"""Run the real fixed-query parser and USB syscall paths without hardware."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#define _POSIX_C_SOURCE 200809L
#define _FILE_OFFSET_BITS 64
#define _TIME_BITS 64
#include <assert.h>
#include <stdarg.h>
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
static const uint8_t descriptors[71] = {
    18,1,0,2,0,0,0,64,4,30,136,136,0,0,1,2,0,1,
    9,2,53,0,1,1,0,160,250,9,4,0,0,5,255,255,255,0,
    7,5,1,2,0,2,0,7,5,130,2,0,2,0,
    7,5,3,2,64,0,0,7,5,131,2,64,0,0,7,5,132,2,0,2,0
};
enum failure { NONE, KERNEL, COMPAT, ATTRIBUTE, BINDING, DESCRIPTOR,
    BUS, NUMBER, NODE, NODE_DESCRIPTOR, CLAIM, RELEASE, TX_SHORT,
    TX_ERROR, RX_ERROR, STALE_THEN_REPLY, STALE_FOREVER, DEADLINE,
    MALFORMED, ACK, FAILURE_ACK, LONG_FILE };
static enum failure failure;
static unsigned sends, receives, claims, releases, closes, clocks;
static uint16_t pending_wid;
static uint8_t pending_seq;
static size_t file_offset;
static const uint8_t *file_data;
static size_t file_size;
static const char compatible[] = "tianyi,ty1208z-ca-usb-host-experiment\0hi3798mv100-series";
static int mock_open(const char *path, int flags, ...) {
    file_offset = 0;
    if (!strcmp(path, "/dev/bus/usb/001/002")) {
        assert(flags == (O_RDWR | O_CLOEXEC));
        if (failure == NODE) { errno = EACCES; return -1; }
        file_data = descriptors; file_size = sizeof(descriptors); return 100;
    }
    assert(flags == (O_RDONLY | O_CLOEXEC));
    if (!strcmp(path, "/sys/firmware/devicetree/base/compatible")) {
        file_data = (const uint8_t *)compatible; file_size = sizeof(compatible);
        if (failure == COMPAT) file_size--;
        if (failure == LONG_FILE) file_size = 513;
        return 10;
    }
    assert(!strncmp(path, RDA_SYSFS_PREFIX, strlen(RDA_SYSFS_PREFIX)));
    const char *name = path + strlen(RDA_SYSFS_PREFIX);
    const char *value = NULL;
    if (!strcmp(name,"idVendor")) value = failure == ATTRIBUTE ? "ffff\n" : "1e04\n";
    else if (!strcmp(name,"idProduct")) value = "8888\n";
    else if (!strcmp(name,"bcdDevice")) value = "0000\n";
    else if (!strcmp(name,"speed")) value = "480\n";
    else if (!strcmp(name,"bConfigurationValue")) value = "1\n";
    else if (!strcmp(name,"busnum")) value = failure == BUS ? "2\n" : "1\n";
    else if (!strcmp(name,"devnum")) value = failure == NUMBER ? "2x\n" : "2\n";
    else if (!strcmp(name,"descriptors")) {
        file_data = descriptors; file_size = sizeof(descriptors);
        if (failure == DESCRIPTOR) file_size--;
        return 10;
    } else assert(0);
    file_data = (const uint8_t *)value; file_size = strlen(value); return 10;
}
static ssize_t mock_read(int fd, void *out, size_t size) {
    assert(fd == 10 || fd == 100);
    if (failure == LONG_FILE && file_size == 513) {
        size_t n = file_size - file_offset;
        if (n > size) n = size;
        memset(out, 0, n); file_offset += n; return (ssize_t)n;
    }
    size_t n = file_size - file_offset;
    if (n > size) n = size;
    memcpy(out, file_data + file_offset, n); file_offset += n;
    if (fd == 100 && failure == NODE_DESCRIPTOR) ((uint8_t *)out)[8] ^= 1;
    return (ssize_t)n;
}
static int mock_close(int fd) { assert(fd == 10 || fd == 100); closes++; return 0; }
static int mock_uname(struct utsname *name) {
    strcpy(name->release, failure == KERNEL ? "other" : "6.12.112-ty1208z-usb-host1"); return 0;
}
static int mock_lstat(const char *path, struct stat *data) {
    (void)data; assert(!strcmp(path,"/sys/bus/usb/devices/1-2:1.0/driver"));
    if (failure == BINDING) return 0;
    errno = ENOENT; return -1;
}
static int mock_clock_gettime(clockid_t clock, struct timespec *now) {
    assert(clock == CLOCK_MONOTONIC);
    now->tv_sec = failure == DEADLINE && clocks % 2 ? 3 : 0;
    now->tv_nsec = 0; clocks++; return 0;
}
static int mock_ioctl(int fd, unsigned long operation, ...) {
    assert(fd == 100);
    va_list args; va_start(args, operation); void *arg = va_arg(args, void *); va_end(args);
    if (operation == USBDEVFS_CLAIMINTERFACE || operation == USBDEVFS_RELEASEINTERFACE) {
        assert(*(unsigned int *)arg == 0);
        if (operation == USBDEVFS_CLAIMINTERFACE) {
            claims++; if (failure == CLAIM) { errno = EBUSY; return -1; }
        } else {
            releases++; if (failure == RELEASE) { errno = EIO; return -1; }
        }
        return 0;
    }
    /* Any control/reset/disconnect/configuration ioctl fails this assertion. */
    assert(operation == USBDEVFS_BULK);
    struct usbdevfs_bulktransfer *transfer = arg;
    assert(transfer->timeout > 0 && transfer->timeout <= 2000);
    if (transfer->ep == 1) {
        assert(transfer->len == 8 && transfer->timeout == 500);
        uint8_t *p = transfer->data;
        assert(p[0] == 8 && p[1] == 0x40 && p[2] == 'Q' && p[4] == 6 && !p[5]);
        pending_wid = rda_id_le16(p + 6); pending_seq = p[3];
        assert(pending_wid == RDA_ID_STATE || pending_wid == RDA_ID_REVISION || pending_wid == RDA_ID_FIRMWARE);
        sends++;
        if (failure == TX_SHORT) return 7;
        if (failure == TX_ERROR) { errno = EPIPE; return -1; }
        return 8;
    }
    assert(transfer->ep == 0x82 && transfer->len == 512);
    receives++;
    if (failure == RX_ERROR) { errno = ETIMEDOUT; return -1; }
    uint8_t *p = transfer->data;
    size_t size = pending_wid == RDA_ID_STATE ? 4 : pending_wid == RDA_ID_REVISION ? 1 : 20;
    uint16_t reply = pending_wid;
    if (failure == ACK || failure == FAILURE_ACK) { size = 1; reply = 5; }
    memset(p,0,512); p[0] = (uint8_t)(9 + size); p[1] = 0x30; p[2] = 'R'; p[3] = pending_seq;
    p[4] = (uint8_t)(7 + size); p[6] = (uint8_t)reply; p[7] = reply >> 8; p[8] = (uint8_t)size;
    memset(p + 9, 1, size);
    if (failure == FAILURE_ACK) p[9] = 0;
    if (failure == STALE_FOREVER || (failure == STALE_THEN_REPLY && receives % 2)) p[3]--;
    if (failure == MALFORMED) p[4]++;
    return (int)(9 + size);
}
#define open mock_open
#define read mock_read
#define close mock_close
#define uname mock_uname
#define lstat mock_lstat
#define clock_gettime mock_clock_gettime
#define ioctl mock_ioctl
#define main identity_main
#include "rda_usb_identity.c"
#undef main
static void reset(enum failure next) {
    failure = next; sends = receives = claims = releases = closes = clocks = 0;
}
static void parser_tests(void) {
    uint8_t out[20], request[8], descriptor[71];
    const uint16_t wids[] = {RDA_ID_STATE, RDA_ID_REVISION, RDA_ID_FIRMWARE};
    assert(rda_id_query(RDA_ID_STATE,0,NULL) == -EINVAL);
    for (unsigned wid = 0; wid <= 65535; wid++) {
        memset(request,0xa5,8);
        int result = rda_id_query((uint16_t)wid,7,request);
        bool allowed = wid == RDA_ID_STATE || wid == RDA_ID_REVISION || wid == RDA_ID_FIRMWARE;
        assert(result == (allowed ? 8 : -EPERM));
        if (!allowed) for (unsigned i = 0; i < 8; i++) assert(request[i] == 0xa5);
    }
    assert(!rda_id_descriptors(descriptors,71));
    for (unsigned size = 0; size < 71; size++) assert(rda_id_descriptors(descriptors,size) < 0);
    for (unsigned i = 0; i < 71; i++) {
        memcpy(descriptor,descriptors,71); descriptor[i] ^= 1;
        assert(rda_id_descriptors(descriptor,71) < 0);
    }
    memcpy(descriptor,descriptors,71); descriptor[45] = 1;
    assert(rda_id_descriptors(descriptor,71) < 0);
    for (unsigned w = 0; w < 3; w++) {
        size_t size = w == 0 ? 4 : w == 1 ? 1 : 20;
        for (size_t extra = 0; extra <= 3; extra++) {
            size_t n = 9 + size + extra;
            uint8_t *p = calloc(n,1); assert(p);
            p[0] = (uint8_t)(9 + size); p[1] = 0x30; p[2] = 'R'; p[3] = 7;
            p[4] = (uint8_t)(7 + size); p[6] = (uint8_t)wids[w]; p[7] = wids[w] >> 8; p[8] = (uint8_t)size;
            memset(p + 9,0x13,size);
            assert(rda_id_response(p,n,wids[w],7,out) == (int)size);
            for (size_t i = 0; i < 9 + size; i++) {
                /* Exact allocations make every truncated input an ASan boundary. */
                uint8_t *shortp = malloc(i ? i : 1); assert(shortp); memcpy(shortp,p,i);
                memset(out,0xa5,20); assert(rda_id_response(shortp,i,wids[w],7,out) < 0);
                for (unsigned j = 0; j < 20; j++) assert(out[j] == 0xa5);
                free(shortp);
            }
            assert(rda_id_response(p,n,wids[w],8,out) == -EAGAIN);
            assert(rda_id_response(p,n,wids[w],7,NULL) == -EINVAL);
            p[8]++; assert(rda_id_response(p,n,wids[w],7,out) < 0); p[8]--;
            p[4]++; assert(rda_id_response(p,n,wids[w],7,out) < 0); p[4]--;
            if (extra) { p[n-1] = 1; assert(rda_id_response(p,n,wids[w],7,out) < 0); }
            free(p);
        }
    }
    uint8_t ack[] = {10,0x30,'R',7,8,0,5,0,1,1};
    assert(rda_id_response(ack,10,RDA_ID_STATE,7,out) == -ENODATA);
    ack[9] = 0; assert(rda_id_response(ack,10,RDA_ID_STATE,7,out) == -EREMOTEIO);
    assert(rda_id_response(NULL,0,RDA_ID_STATE,7,out) < 0);
    /* Arbitrary lengths, headers and typed sizes must remain memory-safe. */
    uint32_t random = 0x1285995;
    for (unsigned i = 0; i < 30000; i++) {
        size_t n = i % 514; uint8_t *p = malloc(n ? n : 1); assert(p);
        for (size_t j = 0; j < n; j++) { random = random * 1664525 + 1013904223; p[j] = random >> 24; }
        (void)rda_id_response(p,n,wids[i % 3],7,out); free(p);
    }
}
int main(void) {
    parser_tests();
    char *probe[] = {"rda-usb-identity","--probe"};
    char *test[] = {"rda-usb-identity","--selftest"};
    reset(NONE); assert(!identity_main(2,test)); assert(!closes && !clocks && !claims && !sends);
    reset(NONE); assert(identity_main(1,probe) == 2); assert(!claims && !sends);
    reset(NONE); assert(!identity_main(2,probe)); assert(sends == 3 && receives == 3 && claims == 1 && releases == 1);
    for (enum failure f = KERNEL; f <= LONG_FILE; f++) {
        reset(f); int result = identity_main(2,probe);
        assert(result == (f == STALE_THEN_REPLY ? 0 : 1));
        if (f <= NODE_DESCRIPTOR || f == LONG_FILE) assert(!claims && !sends && !receives);
        else if (f == CLAIM) assert(claims == 1 && !sends && !releases);
        else { assert(claims == 1 && sends == 3 && releases == 1); }
        if (f == STALE_FOREVER) assert(receives == 15);
        if (f == STALE_THEN_REPLY) assert(receives == 6);
        if (f == TX_ERROR || f == TX_SHORT || f == DEADLINE) assert(!receives);
    }
    puts("RDA_USB_IDENTITY_REGRESSION_PASS actual-parser actual-syscalls fixed-query-only bounded-timeout no-hardware");
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="rda-identity-") as directory:
    base = Path(directory)
    source = base / "test.c"
    source.write_text("#include <stdbool.h>\n#define RDA_SYSFS_PREFIX \"/sys/bus/usb/devices/1-2/\"\n" + HARNESS)
    program = base / "test"
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-no-pie",
                    "-I", str(ROOT / "tools"), str(source), "-o", str(program)], check=True)
    result = subprocess.run([str(program)], check=True, capture_output=True, text=True)
    print(result.stdout.splitlines()[-1])
