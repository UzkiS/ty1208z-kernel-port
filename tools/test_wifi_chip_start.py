#!/usr/bin/env python3
"""Run actual RDA chip startup, version getters and reply parsers under sanitizers."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
args = parser.parse_args()
root = args.source / "rdawlan"
files = {name: (root / name).read_text() for name in (
    "wland_wid.c", "wland_cmds.c", "wland_wid.h", "wland_dev.h", "wland_defs.h", "wland_fweh.h")}


def definition(filename, name):
    text = files[filename]
    spans = function_spans(text, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return text[start:end]


def structure(name):
    return re.search(r"^struct " + name + r" \{[\s\S]*?^\};", files["wland_dev.h"], re.M)[0]


header = files["wland_wid.h"]
start = header.index("static inline enum wid_type wland_get_wid_type(")
end = header.index("static inline u8 wland_get_seqidx(", start)
constants = "enum wid_type { WID_CHAR, WID_SHORT, WID_INT, WID_STR, WID_BIN, WID_UNKNOW };\n"
constants += "enum wland_firmw_wid {\n"
for name in ("WID_MEMORY_ADDRESS", "WID_CHIP_VERSION", "WID_FIRMWARE_VERSION", "WID_STATUS",
             "WID_MAX_CHAR_ID", "WID_MAX_SHORT_ID", "WID_MAX_INTEGER_ID", "WID_MAX_STRING_ID",
             "WID_MAX_BINARY_ID", "PKT_TYPE_CFG_RSP", "WLAND_VER_91_H"):
    match = re.search(r"^\s*" + name + r"\s*=\s*([^,\n]+),", "\n".join(files.values()), re.M)
    assert match, name
    constants += name + " = " + match[1] + ",\n"
constants += "};\n"
for name in ("FMW_HEADER_LEN", "WID_HEADER_LEN", "CDC_DCMD_LEN_MASK", "CDC_DCMD_LEN_SHIFT",
             "WLAND_WID_MSG_RESP", "STATUS_SUCCESS", "WLAND_DCMD_MEDLEN", "ROUND_UP_MARGIN",
             "RDA5991H_CODE_ADDR"):
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)", "\n".join(files.values()), re.M)
    assert match, name
    constants += "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"
constants += re.search(r"^#define RETRIES\s+\d+", files["wland_cmds.c"], re.M)[0] + "\n"

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
typedef uint16_t __le16;
#define WLAND_DBG(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
/* CONSTANTS */
/* STRUCTURES */
enum { WLAND_BUS_DATA = 2 };
struct wland_bus { int state, chip, chip_ready; u8 chip_version; };
struct wland_private { struct wland_bus *bus_if; struct wland_proto *prot; int proto_block; };
struct wland_if { struct wland_private *drvr; int ifidx; };
struct net_device { struct wland_if *priv; };
static struct wland_bus bus;
static struct wland_proto proto;
static struct wland_private driver = {&bus, &proto, 0};
static struct wland_if interface = {&driver, 0};
static struct net_device device = {&interface};
static char rdawlan_firmware_path[100];
enum { ACTIVE, MEMORY, CODE, DATA, RUN, PREINIT, SCAN, CHIP, FIRMWARE, CONFIG, OPERATIONS };
enum { VALID, STATUS_ONLY, WRONG_WID, TRUNCATED, ZERO, WRONG_ID, EMPTY_VERSION };
static int errors[OPERATIONS], kinds[OPERATIONS], trace[128], count, lock_depth, receives;
static int firmware_length;
static u32 memory_value;
static char printed_version[32];
static void *netdev_priv(struct net_device *ndev) { return ndev->priv; }
static void mutex_lock(int *lock) { assert(lock == &driver.proto_block && !lock_depth); lock_depth++; }
static void mutex_unlock(int *lock) { assert(lock == &driver.proto_block && lock_depth == 1); lock_depth--; }
static int operation(int op) {
    assert(count < 128 && !bus.chip_ready && bus.chip_version == 0xa5);
    trace[count++] = op; return errors[op];
}
static u16 get_le16(const u8 *p) { return (u16)p[0] | ((u16)p[1] << 8); }
static void put_le16(u8 *p, u16 n) { p[0] = n; p[1] = n >> 8; }
/* REAL TYPE */
/* REAL PARSERS */
static int query_operation(u16 wid) {
    if (wid == WID_MEMORY_ADDRESS) return MEMORY;
    if (wid == WID_CHIP_VERSION) return CHIP;
    assert(wid == WID_FIRMWARE_VERSION); return FIRMWARE;
}
static int wland_wid_hdrpush(struct wland_private *drvr, u16 wid, bool write, void *data, u16 len) {
    assert(drvr == &driver && lock_depth == 1 && !write && data && len);
    operation(query_operation(wid)); proto.cmd = wid; proto.msg.wid_msg_id = ++proto.reqid;
    return 0;
}
static int wland_proto_cdc_msg(struct wland_private *drvr) { assert(drvr == &driver); return 0; }
static int wland_bus_rxctl(struct wland_bus *b, u8 *out, unsigned int capacity) {
    assert(b == &bus && out == (u8 *)&proto.msg && lock_depth == 1); receives++;
    int op = query_operation(proto.cmd), kind = kinds[op];
    if (errors[op]) return errors[op];
    if (kind == ZERO) return 0;
    u16 wid = proto.cmd;
    unsigned int len = op == MEMORY ? 4 : op == CHIP ? 1 : firmware_length;
    if (kind == STATUS_ONLY) { wid = WID_STATUS; len = 1; }
    if (kind == WRONG_WID) wid = WID_STATUS;
    if (kind == EMPTY_VERSION) len = 0;
    unsigned int total = sizeof(proto.msg) + 3 + len;
    assert(total <= capacity);
    put_le16(out, total | (PKT_TYPE_CFG_RSP << CDC_DCMD_LEN_SHIFT));
    out[2] = WLAND_WID_MSG_RESP; out[3] = kind == WRONG_ID ? proto.reqid + 1 : proto.reqid;
    put_le16(out + 4, total - WID_HEADER_LEN);
    put_le16(proto.buf, wid); proto.buf[2] = len;
    if (kind == STATUS_ONLY) proto.buf[3] = STATUS_SUCCESS;
    else if (op == MEMORY) memcpy(proto.buf + 3, &memory_value, 4);
    else if (op == CHIP) proto.buf[3] = 13;
    else memset(proto.buf + 3, 'V', len);
    return kind == TRUNCATED ? total - 1 : total;
}
/* REAL COMPLETION */
/* REAL GETTER */
static int wland_bus_active(struct wland_bus *b) { assert(b == &bus); return operation(ACTIVE); }
static int wland_download_codefile(struct wland_if *ifp) { assert(ifp == &interface); return operation(CODE); }
static int wland_download_datafile(struct wland_if *ifp) { assert(ifp == &interface); return operation(DATA); }
static int wland_run_firmware(struct wland_if *ifp, u32 addr) {
    assert(ifp == &interface && addr == RDA5991H_CODE_ADDR); return operation(RUN);
}
static int wland_preinit_cmds_91h(struct wland_if *ifp) { assert(ifp == &interface); return operation(PREINIT); }
static int wland_set_scan_timeout(struct wland_if *ifp) { assert(ifp == &interface); return operation(SCAN); }
static void wland_config_and_efuse(struct wland_if *ifp) {
    assert(ifp == &interface && !bus.chip_ready && bus.chip_version == 13);
    trace[count++] = CONFIG;
}
static void pr_err(const char *format, ...) {
    va_list args; va_start(args, format);
    if (strstr(format, "Firmware")) {
        const char *version = va_arg(args, const char *);
        assert(strlen(version) == (unsigned)firmware_length);
        strcpy(printed_version, version);
    }
    va_end(args);
}
/* REAL START */
static void reset(void) {
    memset(&bus, 0, sizeof(bus)); memset(&proto, 0, sizeof(proto));
    memset(errors, 0, sizeof(errors)); memset(kinds, 0, sizeof(kinds));
    memset(printed_version, 0, sizeof(printed_version));
    bus.state = WLAND_BUS_DATA; bus.chip = WLAND_VER_91_H; bus.chip_version = 0xa5;
    driver.bus_if = &bus; driver.prot = &proto; interface.drvr = &driver; device.priv = &interface;
    strcpy(rdawlan_firmware_path, "sta"); memory_value = 0; firmware_length = 20;
    count = lock_depth = receives = 0;
}
static void success(void) {
    assert(!wland_start_chip(&device) && !lock_depth && bus.chip_ready && bus.chip_version == 13);
    assert(strlen(printed_version) == (unsigned)firmware_length);
}
int main(void) {
    const int sequence[] = {ACTIVE, MEMORY, CODE, DATA, RUN, PREINIT, SCAN, CHIP, FIRMWARE, CONFIG};
    const int failures[] = {-EIO, -ETIMEDOUT, -EPROTO, -ENOENT};
    for (unsigned i = 0; i < 9; i++) for (unsigned e = 0; e < 4; e++) {
        reset(); errors[sequence[i]] = failures[e];
        assert(wland_start_chip(&device) == failures[e]);
        assert(!lock_depth && !bus.chip_ready && bus.chip_version == 0xa5 && count == (int)i + 1);
        assert(!memcmp(trace, sequence, count * sizeof(trace[0])) && !printed_version[0]);
        memset(errors, 0, sizeof(errors)); count = 0; success();
        assert(count == 10 && !memcmp(trace, sequence, sizeof(sequence)));
    }
    for (int op = MEMORY; op <= FIRMWARE; op++) {
        if (op != MEMORY && op != CHIP && op != FIRMWARE) continue;
        for (int kind = STATUS_ONLY; kind <= WRONG_ID; kind++) {
            reset(); memory_value = 0xffffffff; kinds[op] = kind;
            assert(wland_start_chip(&device) < 0);
            assert(!lock_depth && !bus.chip_ready && bus.chip_version == 0xa5 && !printed_version[0]);
            assert(trace[count - 1] == op);
            kinds[op] = VALID; count = 0; success();
        }
    }
    reset(); kinds[FIRMWARE] = EMPTY_VERSION;
    assert(wland_start_chip(&device) == -EPROTO && !bus.chip_ready && bus.chip_version == 0xa5);
    for (int len = 1; len <= 20; len++) {
        reset(); firmware_length = len; memory_value = 0xffffffff; success();
        assert(count == 7 && trace[2] == PREINIT && trace[3] == SCAN);
    }
    for (unsigned mode = 0; mode < 2; mode++) {
        reset(); strcpy(rdawlan_firmware_path, mode ? "p2p" : "ap"); success();
        assert(count == (mode ? 10 : 7));
        if (!mode) assert(trace[5] == CHIP && trace[6] == FIRMWARE);
    }
    const char *invalid[] = {"rf", "sta-extra", "ap/../rf", "", "STA"};
    for (unsigned i = 0; i < sizeof(invalid)/sizeof(invalid[0]); i++) {
        reset(); strcpy(rdawlan_firmware_path, invalid[i]);
        assert(wland_start_chip(&device) == -EPERM && !count && !bus.chip_ready && bus.chip_version == 0xa5);
    }
    reset(); assert(wland_start_chip(NULL) == -ENODEV);
    device.priv = NULL; assert(wland_start_chip(&device) == -ENODEV);
    device.priv = &interface; interface.drvr = NULL; assert(wland_start_chip(&device) == -ENODEV);
    interface.drvr = &driver; driver.bus_if = NULL; assert(wland_start_chip(&device) == -ENODEV);
    reset(); bus.chip_ready = 1;
    assert(!wland_start_chip(&device) && !count && bus.chip_version == 0xa5);
    reset(); bus.chip = 2; success();
    assert(count == 3 && trace[0] == ACTIVE && trace[1] == CHIP && trace[2] == FIRMWARE);
    puts("RDA_CHIP_START_PASS: actual startup/getter/parsers, stage errors/retry, status-only/malformed replies, bounded versions and deferred READY/revision");
}
'''
code = code.replace("/* CONSTANTS */", constants)
code = code.replace("/* STRUCTURES */", structure("wland_dcmd") + "\n" + structure("wland_proto"))
code = code.replace("/* REAL TYPE */", header[start:end])
code = code.replace("/* REAL PARSERS */", definition("wland_cmds.c", "wland_pull_wid") + "\n"
                    + definition("wland_cmds.c", "wland_wid_hdrpull"))
code = code.replace("/* REAL COMPLETION */", definition("wland_cmds.c", "wland_proto_cdc_cmplt"))
code = code.replace("/* REAL GETTER */", definition("wland_cmds.c", "wland_fil_get_cmd_data"))
code = code.replace("/* REAL START */", definition("wland_wid.c", "wland_start_chip"))
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "chip-start.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-sign-compare",
                    str(temp / "chip-start.c"), "-o", str(temp / "chip-start")], check=True)
    subprocess.run([str(temp / "chip-start")], check=True)
print("Chip startup acknowledgement and version publication checks passed; no hardware/firmware acceptance")
