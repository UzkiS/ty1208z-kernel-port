#!/usr/bin/env python3
"""Exercise actual RDA control parsing and USB receive paths under sanitizers."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
args = parser.parse_args()
source = args.source / "rdawlan"
files = {name: (source / name).read_text() for name in (
    "wland_cmds.c", "wland_wid.h", "wland_dev.h", "wland_defs.h", "wland_fweh.h",
    "wland_usb.c", "wland_rx.c")}


def definition(filename, name):
    text = files[filename]
    spans = function_spans(text, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return text[start:end]


def macro(name):
    text = "\n".join(files.values())
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)", text, re.M)
    assert match, name
    return "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"


def structure(name):
    match = re.search(r"^struct " + name + r" \{[\s\S]*?^\};", files["wland_dev.h"], re.M)
    assert match, name
    return match[0]


wid_header = files["wland_wid.h"]
type_start = wid_header.index("static inline enum wid_type wland_get_wid_type(")
type_end = wid_header.index("static inline u8 wland_get_seqidx(", type_start)
wid_type = wid_header[type_start:type_end]
thresholds = re.findall(r"^\s*(WID_MAX_\w+_ID)\s*=\s*([^,\n]+),", wid_header, re.M)
assert len(thresholds) == 5
status = re.search(r"^\s*WID_STATUS\s*=\s*([^,\n]+),", wid_header, re.M)
assert status
constants = "enum wland_firmw_wid {\n" + "".join(f"{name} = {value},\n" for name, value in thresholds)
constants += "WID_STATUS = " + status[1] + "\n};\n"
constants += "enum wid_type { WID_CHAR, WID_SHORT, WID_INT, WID_STR, WID_BIN, WID_UNKNOW };\n"
constants += "\n".join(macro(name) for name in (
    "FMW_HEADER_LEN", "WID_HEADER_LEN", "CDC_DCMD_LEN_MASK", "CDC_DCMD_LEN_SHIFT",
    "WLAND_WID_MSG_RESP", "STATUS_SUCCESS", "WLAND_DCMD_MEDLEN", "ROUND_UP_MARGIN"))
packet_type = re.search(r"^\s*PKT_TYPE_CFG_RSP\s*=\s*([^,\n]+),", wid_header, re.M)
assert packet_type
constants += "enum { PKT_TYPE_CFG_RSP = " + packet_type[1] + " };\n"
retry = re.search(r"^#define RETRIES\s+(\d+)", files["wland_cmds.c"], re.M)
assert retry
constants += "#define RETRIES " + retry[1] + "\n"

# Verify the actual RX dispatcher checks both source and destination before copy.
rx = files["wland_rx.c"]
start = rx.index("if (skb->len < WID_HEADER_LEN)")
assert start < rx.index("rx_len = (u16) (buf[0]", start)
start = rx.index("if (rx_len < sizeof(struct wland_dcmd))")
assert start < rx.index("msg_type = buf[2];", start)
start = rx.index("if (!rx_info->rxbuf || rx_len > rx_info->rxblen)")
assert start < rx.index("memcpy(rx_info->rxctl, skb->data, rx_len);", start)

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
typedef uint16_t __le16;
#define WLAND_DBG(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
/* CONSTANTS */
/* STRUCTURES */
enum { WLAND_BUS_DATA = 2, USB_STATE_UP = 1 };
struct wland_bus { int state; };
struct wland_private { struct wland_proto *prot; struct wland_bus *bus_if; };
static u16 get_le16(const u8 *p) { return (u16)p[0] | ((u16)p[1] << 8); }
static void put_le16(u8 *p, u16 n) { p[0] = n; p[1] = n >> 8; }
/* TYPE */
/* PARSERS */
static int receives, response_result[8];
static u8 response_ids[8];
static int wland_bus_rxctl(struct wland_bus *bus, u8 *buf, unsigned int capacity) {
    (void)bus; assert(receives < 8);
    int index = receives++;
    if (response_result[index] >= 4 && capacity >= 4) buf[3] = response_ids[index];
    return response_result[index];
}
/* COMPLETION */
struct device { int unused; };
struct wland_rx_info { u8 *rxctl; u32 rxlen, rxblen; int rxctl_lock; };
struct wland_usbdev_info {
    struct wland_rx_info *rx_info;
    struct { int state; } bus_pub;
    unsigned long ctl_op;
    bool ctl_completed;
};
static struct wland_usbdev_info usb_device;
static int wait_result;
static struct wland_usbdev_info *wland_usb_get_businfo(struct device *d) { (void)d; return &usb_device; }
static int wland_usb_data_resp_wait(struct wland_usbdev_info *d) { (void)d; return wait_result; }
static bool test_and_set_bit(int bit, unsigned long *value) {
    bool old = (*value & (1UL << bit)) != 0; *value |= 1UL << bit; return old;
}
static void clear_bit(int bit, unsigned long *value) { *value &= ~(1UL << bit); }
#define spin_lock_bh(x) ((void)(x))
#define spin_unlock_bh(x) ((void)(x))
/* USB */
static void rejected(const u8 *bytes, u16 count) {
    u16 wid = 0xa5, size = 0xa5; const u8 *data = (const u8 *)1;
    assert(wland_pull_wid(bytes, count, &wid, &data, &size) < 0);
    assert(wid == 0 && data == NULL && size == 0);
}
static void prefix_checks(const u8 *valid, unsigned int length) {
    for (unsigned int size = 0; size < length; size++) {
        u8 *short_buffer = malloc(size ? size : 1); assert(short_buffer);
        memcpy(short_buffer, valid, size);
        if (size == 2) {
            u16 wid, value_len; const u8 *value;
            assert(wland_pull_wid(short_buffer, 2, &wid, &value, &value_len) == 2);
            assert(!value && value_len == 0);
        } else rejected(short_buffer, size);
        free(short_buffer);
    }
}
static int response(struct wland_private *driver, const u8 *record, u16 count) {
    u8 *packet = (u8 *)&driver->prot->msg;
    unsigned int total = sizeof(driver->prot->msg) + count;
    memset(&driver->prot->msg, 0, sizeof(driver->prot->msg));
    put_le16(packet, (PKT_TYPE_CFG_RSP << CDC_DCMD_LEN_SHIFT) | total);
    packet[2] = WLAND_WID_MSG_RESP;
    put_le16(packet + 4, total - WID_HEADER_LEN);
    memcpy(driver->prot->buf, record, count);
    return wland_wid_hdrpull(driver, packet, total);
}
int main(void) {
    assert(sizeof(struct wland_dcmd) == 6);
    const u8 small[] = {0x01,0x00,1,0x7f};
    const u8 word[] = {0x01,0x10,2,0x34,0x12};
    const u8 integer[] = {0x01,0x20,4,1,2,3,4};
    const u8 string[] = {0x01,0x30,3,'a','b','c'};
    const u8 binary[] = {0x01,0x40,3,0,1,2,3,6};
    const u8 *valid[] = {small,word,integer,string,binary};
    const unsigned int lengths[] = {4,5,7,6,8}, values[] = {1,2,4,3,3};
    for (unsigned int i = 0; i < 5; i++) {
        u16 wid, size; const u8 *data;
        assert(wland_pull_wid(valid[i], lengths[i], &wid, &data, &size) == (int)lengths[i]);
        assert(size == values[i] && data >= valid[i] && data + size <= valid[i] + lengths[i]);
        prefix_checks(valid[i], lengths[i]);
    }
    rejected(NULL, 0);
    const u8 bad_word[] = {1,0x10,1,0}; rejected(bad_word, sizeof(bad_word));
    const u8 unknown[] = {1,0xff,1,0}; rejected(unknown, sizeof(unknown));
    u8 bad_checksum[sizeof(binary)]; memcpy(bad_checksum, binary, sizeof(binary));
    bad_checksum[7]++; rejected(bad_checksum, sizeof(bad_checksum));
    struct wland_proto proto = {0};
    struct wland_bus bus = {.state = WLAND_BUS_DATA};
    struct wland_private driver = {.prot = &proto, .bus_if = &bus};
    proto.cmd = 0x1001;
    assert(response(&driver, word, sizeof(word)) == 0);
    assert(proto.offset == 3 && proto.rsplen == 2);
    assert(!memcmp(proto.buf + proto.offset, word + 3, 2));
    assert(response(&driver, integer, sizeof(integer)) == -EPROTO);
    assert(proto.offset == 0 && proto.rsplen == 0);
    proto.cmd = 0x4001;
    assert(response(&driver, binary, sizeof(binary)) == 0 && proto.offset == 4 && proto.rsplen == 3);
    const u8 ok[] = {WID_STATUS,0,1,STATUS_SUCCESS};
    const u8 fail[] = {WID_STATUS,0,1,0};
    assert(response(&driver, ok, sizeof(ok)) == 0 && proto.rsplen == 0);
    assert(response(&driver, fail, sizeof(fail)) == -EREMOTEIO);
    u8 *packet = (u8 *)&proto.msg;
    for (unsigned int cut = 0; cut < sizeof(proto.msg) + sizeof(ok); cut++) {
        assert(response(&driver, ok, sizeof(ok)) == 0);
        assert(wland_wid_hdrpull(&driver, packet, cut) < 0);
        assert(proto.offset == 0 && proto.rsplen == 0);
    }
    assert(response(&driver, word, sizeof(word)) == -EPROTO);
    proto.cmd = 0x1001; assert(response(&driver, word, sizeof(word)) == 0);
    put_le16(packet + 4, 4); assert(wland_wid_hdrpull(&driver, packet, 11) == -EMSGSIZE);
    assert(response(&driver, word, sizeof(word)) == 0);
    packet[2] = 'I'; assert(wland_wid_hdrpull(&driver, packet, 11) == -EPROTO);
    assert(response(&driver, word, sizeof(word)) == 0);
    packet[1] = 0x10; assert(wland_wid_hdrpull(&driver, packet, 11) == -EPROTO);
    assert(response(&driver, word, sizeof(word)) == 0);
    assert(wland_wid_hdrpull(&driver, packet, 14) == 0); /* USB trailing padding */
    receives = 0; response_result[0] = 10; response_ids[0] = 7;
    assert(wland_proto_cdc_cmplt(&driver, 7, 32) == 10 && receives == 1);
    receives = 0; response_result[0] = 5; proto.msg.wid_msg_id = 7;
    assert(wland_proto_cdc_cmplt(&driver, 7, 32) == -EMSGSIZE && receives == 1);
    receives = 0; response_result[0] = 33;
    assert(wland_proto_cdc_cmplt(&driver, 7, 32) == -EMSGSIZE && receives == 1);
    receives = 0; response_result[0] = -ETIMEDOUT;
    assert(wland_proto_cdc_cmplt(&driver, 7, 32) == -ETIMEDOUT && receives == 1);
    receives = 0;
    for (unsigned int i = 0; i < RETRIES; i++) { response_result[i] = 10; response_ids[i] = 6; }
    assert(wland_proto_cdc_cmplt(&driver, 7, 32) == -EPROTO && receives == RETRIES);
    receives = 0; response_ids[0] = 255; response_ids[1] = 0;
    assert(wland_proto_cdc_cmplt(&driver, 0, 32) == 10 && receives == 2);
    receives = 0; assert(wland_proto_cdc_cmplt(&driver, 7, 5) == -EMSGSIZE && receives == 0);
    struct wland_rx_info rx = {0}; u8 in[10] = {0}, out[5];
    struct device dev = {0}; wait_result = 1;
    usb_device.rx_info = &rx; usb_device.bus_pub.state = USB_STATE_UP;
    rx.rxctl = in; rx.rxlen = 10; rx.rxblen = sizeof(in); memset(out, 0xa5, sizeof(out));
    assert(wland_usb_bus_rxctl(&dev, out, sizeof(out)) == -EMSGSIZE && rx.rxlen == 0);
    for (unsigned int i = 0; i < sizeof(out); i++) assert(out[i] == 0xa5);
    rx.rxlen = 4; assert(wland_usb_bus_rxctl(&dev, out, sizeof(out)) == 4);
    assert(!memcmp(out, in, 4));
    rx.rxlen = 4; rx.rxblen = 3;
    assert(wland_usb_bus_rxctl(&dev, out, sizeof(out)) == -EMSGSIZE);
    wait_result = 0; assert(wland_usb_bus_rxctl(&dev, out, sizeof(out)) == -ETIMEDOUT);
    puts("RDA_CONTROL_PASS: truncated/typed/checksummed WIDs, response envelopes, bounded IDs, USB copy");
}
'''
code = code.replace("/* CONSTANTS */", constants)
code = code.replace("/* STRUCTURES */", structure("wland_dcmd") + "\n" + structure("wland_proto"))
code = code.replace("/* TYPE */", wid_type)
code = code.replace("/* PARSERS */", "\n".join(definition("wland_cmds.c", name) for name in (
    "wland_pull_wid", "wland_wid_hdrpull")))
code = code.replace("/* COMPLETION */", definition("wland_cmds.c", "wland_proto_cdc_cmplt"))
code = code.replace("/* USB */", definition("wland_usb.c", "wland_usb_bus_rxctl"))
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "test.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-sign-compare", str(temp / "test.c"),
                    "-o", str(temp / "test")], check=True)
    subprocess.run([str(temp / "test")], check=True)
