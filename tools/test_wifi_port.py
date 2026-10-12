#!/usr/bin/env python3
"""Exercise ported production guards/key handling without wireless hardware."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True, help="Patched RDA source")
args = parser.parse_args()
source = args.source / "rdawlan"
files = {path.name: path.read_text() for path in source.glob("*.[ch]")}
blocked = ("wland_efuse_set_vendor_id", "wland_write_efuse_xtal_cal_val",
           "wland_efuse_set_mac_addr", "wland_write_txpower_to_efuse", "wland_rf_test_cmd")
for name in blocked:
    assert name + "(" not in files["wland_rf.c"] and name + " (" not in files["wland_rf.c"]
assert "RDA5995_TESTMODE_FILE" not in files["wland_wid.c"]
assert 'strcpy(rdawlan_firmware_path, "rf")' not in files["wland_wid.c"]
assert "wland_android_priv_cmd(ndev," not in files["wland_linux.c"]
assert "wland_rf_test_cmd(ndev," not in files["wland_linux.c"]
assert "WID_SET_EFUSE_ONE_PAGE" not in files["wland_rf.c"]
assert "struct timespec ts" not in files["wland_cfg80211.c"]
assert "get_fs()" not in files["wland_nvram.c"] + files["wland_cmds.c"]


def extract(filename, name):
    text = files[filename]
    spans = function_spans(text, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return text[start:end]


assert "cfg80211_put_bss(wiphy, bss_internal)" not in extract("wland_cfg80211.c", "wland_bss_roaming_done")
push = extract("wland_cmds.c", "wland_push_wid")
# The real function must reject all prohibited WIDs before writing a message.
assert push.index("return -EPERM;") < push.index("put_le16(buf, WID)")
single = extract("wland_cmds.c", "wland_wid_hdrpush")
assert single.index("return -EPERM;") < single.index("prot->cmd = wid;")
code = extract("wland_trap.c", "wland_download_codefile")
data = extract("wland_trap.c", "wland_download_datafile")
for text in (code, data):
    assert "_RF;" not in text
    assert text.index("return -EPERM;") < text.index("wland_download_image(")
key = files["wland_port_key.h"]
harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
#define WLAND_DBG(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
#define DCMD 0
#define TRACE 0
#define WID_SET_EFUSE_ONE_PAGE 0x210c
#define WID_EFUSE_XTAL_CAL_VAL 0x1402
#define WID_EFUSE_PHY_TXPOW_VAL 0x4311
#define WID_GET_EFUSE_ALL_PAGE 0x4312
enum wid_type { WID_CHAR, WID_SHORT, WID_INT, WID_STR, WID_BIN, WID_UNKNOW };
static enum wid_type wland_get_wid_type(u16 wid) { (void)wid; return WID_STR; }
static u16 wland_get_wid_size(enum wid_type type, u16 len) { (void)type; return len; }
static void put_le16(u8 *p, u16 value) { p[0] = value; p[1] = value >> 8; }
static void put_le32(u8 *p, u32 value) { memcpy(p, &value, 4); }
/* KEY */
/* PUSH */
int main(void) {
    u8 out[32], message[128], secret[32];
    for (int i = 0; i < 32; i++) secret[i] = i;
    for (int len = 0; len <= 40; len++) {
        u8 keybuf[40]; memcpy(keybuf, secret, 32);
        memset(out, 0xa5, sizeof(out));
        bool valid = len == 5 || len == 13 || len == 16 || len == 32;
        assert(wland_port_copy_key(out, keybuf, len, false) == (valid ? 0 : -EINVAL));
        if (valid) {
            assert(!memcmp(out, secret, len));
            for (int i = len; i < 32; i++) assert(out[i] == 0);
        }
    }
    /* Exact short buffers under ASan detect the old unconditional 32-byte read. */
    u8 wep[5] = {1,2,3,4,5}, ccmp[16] = {0};
    assert(!wland_port_copy_key(out, wep, 5, true));
    assert(!wland_port_copy_key(out, ccmp, 16, true));
    assert(!wland_port_copy_key(out, secret, 32, true));
    assert(!memcmp(out, secret, 16));
    assert(!memcmp(out + 16, secret + 24, 8));
    assert(!memcmp(out + 24, secret + 16, 8));
    assert(wland_port_copy_key(out, NULL, 16, false) == -EINVAL);
    const u16 prohibited[] = {0x210c, 0x1402, 0x4311};
    for (unsigned int i = 0; i < sizeof(prohibited)/sizeof(prohibited[0]); i++) {
        memset(message, 0xa5, sizeof(message));
        assert(wland_push_wid(message, prohibited[i], secret, 4, false) == -EPERM);
        for (unsigned int j = 0; j < sizeof(message); j++) assert(message[j] == 0xa5);
        assert(wland_push_wid(message, prohibited[i], NULL, 0, true) == 2);
    }
    assert(wland_push_wid(message, WID_GET_EFUSE_ALL_PAGE, NULL, 0, true) == 2);
    assert(wland_push_wid(message, 0x3001, secret, 16, false) == 19);
    assert(!memcmp(message + 3, secret, 16));
    puts("RDA_PORT_GUARDS_PASS: actual WID packer, short keys, TKIP MIC order, manufacturing exclusion");
}
'''.replace("/* KEY */", key).replace("/* PUSH */", push)
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "test.c").write_text(harness)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-type-limits", str(temp / "test.c"),
                    "-o", str(temp / "test")], check=True)
    subprocess.run([str(temp / "test")], check=True)
print("RDA production source gates passed; no hardware/firmware test")
