#!/usr/bin/env python3
"""Exercise actual cfg80211 PTK/GTK callbacks and firmware-error propagation."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--linux", type=Path, required=True, help="Pinned Linux source")
args = parser.parse_args()
root = args.source / "rdawlan"
cfg = (root / "wland_cfg80211.c").read_text()
dev = (root / "wland_dev.h").read_text()
wid = (root / "wland_wid.h").read_text()
ieee = (args.linux / "include/linux/ieee80211.h").read_text()
nl = (args.linux / "include/uapi/linux/nl80211.h").read_text()
kernel_cfg = (args.linux / "include/net/cfg80211.h").read_text()


def definition(name):
    spans = function_spans(cfg, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return cfg[start:end]


def structure(name):
    match = re.search(r"^struct " + name + r" \{[\s\S]*?^\};", dev, re.M)
    assert match, name
    return match[0]


constants = re.search(r"^enum nl80211_iftype \{[\s\S]*?^\};", nl, re.M)[0] + "\n"
suite = re.search(r"^#define SUITE\([^\n]+", ieee, re.M)
assert suite
constants += suite[0] + "\n"
for name in ("WLAN_CIPHER_SUITE_WEP40", "WLAN_CIPHER_SUITE_WEP104", "WLAN_CIPHER_SUITE_TKIP",
             "WLAN_CIPHER_SUITE_CCMP", "WLAN_CIPHER_SUITE_AES_CMAC", "WLAN_MAX_KEY_LEN",
             "DOT11_MAX_DEFAULT_KEYS"):
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)", ieee + kernel_cfg + dev, re.M)
    assert match, name
    constants += "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"
for name in ("WID_ADD_PTK", "WID_ADD_TX_GTK", "WID_ADD_RX_GTK", "WID_P2P_TX_GTK", "WID_P2P_RX_GTK"):
    match = re.search(r"^\s*" + name + r"\s*=\s*([^,\n]+),", wid, re.M)
    assert match, name
    constants += "enum { " + name + " = " + match[1] + " };\n"

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef uint32_t u32; typedef int32_t s32;
#define ETH_ALEN 6
#define MIN(a,b) ((a) < (b) ? (a) : (b))
#define WLAND_DBG(...) (++debug_calls)
#define WLAND_ERR(...) ((void)0)
#define WLAND_DUMP(component,data,length,format,...) mock_dump(data,length,format)
#define WLAND_AP_RESET
/* CONSTANTS */
/* STRUCTURES */
struct key_params { const u8 *key; const u8 *seq; int key_len; int seq_len; u32 cipher; };
struct wiphy { int unused; };
struct wireless_dev { enum nl80211_iftype iftype; };
struct wland_cfg80211_vif { struct wireless_dev wdev; bool tx_gtk_valid; u8 tx_gtk_index; };
struct wland_cfg80211_profile { u8 bssid[ETH_ALEN]; };
struct wland_if;
struct net_device {
    struct wireless_dev *ieee80211_ptr;
    struct wland_if *priv;
    struct wland_cfg80211_profile *profile;
};
struct wland_if { struct net_device *ndev; struct wland_cfg80211_vif *vif; };
static int ap_gtk_len, calls, waits, reply_status, debug_calls, secret_dumps;
static bool ready;
static u32 command_wid;
static size_t command_size;
static u8 command_data[64];
static void mock_dump(const void *data, size_t length, const char *format) {
    (void)data; (void)length;
    if (strstr(format, "Key:")) secret_dumps++;
}
static void *netdev_priv(struct net_device *ndev) { return ndev->priv; }
static struct wland_cfg80211_profile *ndev_to_prof(struct net_device *ndev) { return ndev->profile; }
static bool wland_check_vif_up(struct wland_cfg80211_vif *vif) { (void)vif; return ready; }
static bool is_multicast_ether_addr(const u8 *address) { return address[0] & 1; }
static bool is_valid_ether_addr(const u8 *address) {
    bool any = false;
    for (int i = 0; i < ETH_ALEN; i++) any |= address[i] != 0;
    return any && !is_multicast_ether_addr(address);
}
static void wland_netdev_wait_pend8021x(struct net_device *ndev) { (void)ndev; waits++; }
static int wland_fil_set_cmd_data(struct wland_if *ifp, u32 id, const void *data, size_t size) {
    (void)ifp; assert(size <= sizeof(command_data));
    calls++; command_wid = id; command_size = size; memcpy(command_data, data, size);
    return reply_status;
}
/* HELPERS */
/* FUNCTIONS */
static struct wiphy phy;
static struct wland_cfg80211_vif vif;
static struct wland_cfg80211_profile profile;
static struct net_device netdev = {&vif.wdev, NULL, &profile};
static struct wland_if interface = {&netdev, &vif};
static const u8 peer[6] = {2, 3, 4, 5, 6, 7};
static void reset(enum nl80211_iftype type) {
    netdev.priv = &interface; netdev.ieee80211_ptr = &vif.wdev;
    vif.wdev.iftype = type; memcpy(profile.bssid, peer, sizeof(peer));
    vif.tx_gtk_valid = false; vif.tx_gtk_index = 0;
    ready = true; calls = waits = debug_calls = secret_dumps = 0; reply_status = 0;
    ap_gtk_len = 0x55; command_wid = 0; command_size = 0;
    memset(command_data, 0xa5, sizeof(command_data));
}
static int install(bool pairwise, u8 index, const u8 *address, struct key_params *params) {
    return wland_cfg80211_add_key(&phy, &netdev, -1, index, pairwise, address, params);
}
static void check_payload(enum nl80211_iftype type, bool pairwise, int index,
                          const u8 *key, int length, const u8 *sequence, int seq_length) {
    u8 expected[64] = {0}; size_t offset;
    bool client = type == NL80211_IFTYPE_STATION || type == NL80211_IFTYPE_P2P_CLIENT;
    if (pairwise) {
        assert(command_wid == WID_ADD_PTK); offset = 7;
        memcpy(expected, peer, 6); expected[6] = length;
        assert(waits == (int)client);
    } else if (client) {
        assert(command_wid == (type == NL80211_IFTYPE_STATION ? WID_ADD_RX_GTK : WID_P2P_RX_GTK));
        offset = 16; memcpy(expected, peer, 6);
        if (seq_length) memcpy(expected + 6, sequence, seq_length);
        expected[14] = index; expected[15] = length; assert(!waits);
    } else {
        assert(command_wid == (type == NL80211_IFTYPE_AP ? WID_ADD_TX_GTK : WID_P2P_TX_GTK));
        offset = 2; expected[0] = index; expected[1] = length; assert(!waits);
    }
    memcpy(expected + offset, key, length);
    if (length == 32 && client) {
        memcpy(expected + offset + 16, key + 24, 8);
        memcpy(expected + offset + 24, key + 16, 8);
    }
    assert(calls == 1 && command_size == offset + (size_t)length);
    assert(!memcmp(expected, command_data, command_size));
    for (size_t i = command_size; i < sizeof(command_data); i++) assert(command_data[i] == 0xa5);
}
int main(void) {
    const enum nl80211_iftype roles[] = {NL80211_IFTYPE_STATION, NL80211_IFTYPE_AP,
                                       NL80211_IFTYPE_P2P_CLIENT, NL80211_IFTYPE_P2P_GO};
    const u32 ciphers[] = {WLAN_CIPHER_SUITE_WEP40, WLAN_CIPHER_SUITE_WEP104,
                          WLAN_CIPHER_SUITE_CCMP, WLAN_CIPHER_SUITE_TKIP};
    const int lengths[] = {5, 13, 16, 32};
    u8 sequence[8] = {8,7,6,5,4,3,2,1};
    for (unsigned r = 0; r < 4; r++) for (unsigned c = 0; c < 4; c++) {
        for (int length = -1; length <= 40; length++) {
            u8 *key = malloc(length > 0 ? (size_t)length : 1); assert(key);
            for (int i = 0; i < length; i++) key[i] = (u8)(0x10+i);
            struct key_params params = {key, sequence, length, 8, ciphers[c]};
            for (int pairwise = 0; pairwise <= 1; pairwise++) {
                reset(roles[r]);
                int result = install(pairwise, pairwise ? 0 : 3, peer, &params);
                if (length != lengths[c]) {
                    assert(result == -EINVAL && !calls && !waits && !debug_calls);
                    assert(ap_gtk_len == 0x55);
                    assert(!vif.tx_gtk_valid);
                } else {
                    assert(!result); check_payload(roles[r], pairwise, pairwise ? 0 : 3, key, length, sequence, 8);
                    assert(ap_gtk_len == ((!pairwise && roles[r] == NL80211_IFTYPE_AP) ? length+2 : 0x55));
                    assert(vif.tx_gtk_valid == (!pairwise && roles[r] == NL80211_IFTYPE_AP));
                    if (vif.tx_gtk_valid) assert(vif.tx_gtk_index == 3);
                }
                for (int i = 0; i < length; i++) assert(key[i] == (u8)(0x10+i));
                assert(!secret_dumps);
            }
            free(key);
        }
    }
    u8 key[16] = {1,2,3}; struct key_params params = {key, sequence, 16, 8, WLAN_CIPHER_SUITE_CCMP};
    for (unsigned r = 0; r < 4; r++) for (int pairwise = 0; pairwise <= 1; pairwise++) {
        const int statuses[] = {-EIO, -ETIMEDOUT, -EPROTO, 23};
        for (unsigned i = 0; i < sizeof(statuses)/sizeof(statuses[0]); i++) {
            reset(roles[r]); reply_status = statuses[i];
            assert(install(pairwise, 0, peer, &params) == (reply_status < 0 ? reply_status : 0));
            assert(calls == 1); assert(ap_gtk_len == ((!pairwise && roles[r] == NL80211_IFTYPE_AP && reply_status >= 0) ? 18 : 0x55));
            assert(vif.tx_gtk_valid == (!pairwise && roles[r] == NL80211_IFTYPE_AP && reply_status >= 0));
        }
    }
    for (int len = -1; len <= 40; len++) {
        reset(NL80211_IFTYPE_STATION); params.seq_len = len;
        assert(install(false, 0, peer, &params) == ((len < 0 || len > 8) ? -EINVAL : 0));
        assert(calls == (len >= 0 && len <= 8));
    }
    params.seq_len = 8; params.seq = NULL; reset(NL80211_IFTYPE_STATION);
    assert(install(false, 0, peer, &params) == -EINVAL && !calls);
    params.seq_len = 0; assert(!install(false, 0, peer, &params));
    reset(NL80211_IFTYPE_STATION); params.key = NULL;
    assert(install(true, 0, peer, &params) == -EINVAL && !calls && !debug_calls);
    params.key = key;
    assert(install(true, 0, peer, NULL) == -EINVAL && !calls && !debug_calls);
    for (int index = 4; index < 256; index++) {
        reset(NL80211_IFTYPE_STATION); assert(install(false, index, peer, &params) == -EINVAL && !calls);
    }
    for (int index = 1; index < 4; index++) {
        reset(NL80211_IFTYPE_STATION); assert(install(true, index, peer, &params) == -EOPNOTSUPP && !calls);
    }
    const u8 invalid_peers[][6] = {{0}, {1,2,3,4,5,6}, {255,255,255,255,255,255}};
    for (unsigned i = 0; i < 3; i++) {
        reset(NL80211_IFTYPE_STATION);
        assert(install(true, 0, invalid_peers[i], &params) == -EINVAL && !calls);
        memcpy(profile.bssid, invalid_peers[i], 6);
        assert(install(false, 0, peer, &params) == -EINVAL && !calls);
    }
    reset(NL80211_IFTYPE_STATION); assert(install(true, 0, NULL, &params) == -EINVAL && !calls);
    for (int role = NL80211_IFTYPE_UNSPECIFIED; role < NUM_NL80211_IFTYPES; role++) {
        if (wland_port_key_role(role)) continue;
        reset(role); assert(install(false, 0, peer, &params) == -EOPNOTSUPP && !calls);
    }
    reset(NL80211_IFTYPE_STATION); struct wireless_dev foreign = {NL80211_IFTYPE_AP};
    netdev.ieee80211_ptr = &foreign;
    assert(install(false, 0, peer, &params) == -EINVAL && !calls);
    reset(NL80211_IFTYPE_STATION); ready = false;
    assert(install(false, 0, peer, &params) == -EIO && !calls);
    reset(NL80211_IFTYPE_STATION); params.cipher = WLAN_CIPHER_SUITE_AES_CMAC;
    assert(install(false, 0, peer, &params) == -EOPNOTSUPP && !calls);
    params.cipher = 0x12345678;
    assert(install(false, 0, peer, &params) == -EOPNOTSUPP && !calls);
    reset(NL80211_IFTYPE_STATION); params.cipher = WLAN_CIPHER_SUITE_CCMP;
    assert(wland_cfg80211_add_key(&phy, &netdev, 1, 0, false, peer, &params) == -EOPNOTSUPP && !calls);
    puts("RDA_KEY_CALLBACKS_PASS: actual callbacks, wire payloads/MIC/RSC, parameter rejection, firmware errors and AP cache ordering");
}
'''
code = code.replace("/* CONSTANTS */", constants)
code = code.replace("/* STRUCTURES */", "\n".join(structure(name) for name in ("wland_ptkey", "wland_rx_gtkey")))
code = code.replace("/* HELPERS */", (root / "wland_port_key.h").read_text() +
                    (root / "wland_port_key_validate.h").read_text())
code = code.replace("/* FUNCTIONS */", "\n".join(definition(name) for name in (
    "wland_add_ptkey", "wland_add_gtkey", "wland_cfg80211_add_key")))
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "keys.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-sign-compare",
                    "-Wno-type-limits", str(temp / "keys.c"), "-o", str(temp / "keys")], check=True)
    subprocess.run([str(temp / "keys")], check=True)
print("RDA key callback sanitizer pass; firmware/radio, key deletion and AP stop remain untested")
