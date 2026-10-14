#!/usr/bin/env python3
"""Run actual RDA unsupported operations and AP-stop state transitions."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--linux", type=Path, required=True)
args = parser.parse_args()
root = args.source / "rdawlan"
files = {name: (root / name).read_text() for name in (
    "wland_cfg80211.c", "wland_cfg80211.h", "wland_cmds.c", "wland_dev.h",
    "wland_wid.h", "wland_p2p.h", "wland_defs.h")}
nl = (args.linux / "include/uapi/linux/nl80211.h").read_text()
ieee = (args.linux / "include/linux/ieee80211.h").read_text()


def definition(filename, name):
    text = files[filename]
    spans = function_spans(text, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return text[start:end]


def macro(name):
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)",
                      "\n".join(files.values()) + "\n" + ieee, re.M)
    assert match, name
    return "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"


constants = re.search(r"^enum nl80211_iftype \{[\s\S]*?^\};", nl, re.M)[0] + "\n"
constants += re.search(r"^#define SUITE\([^\n]+", ieee, re.M)[0] + "\n"
constants += re.search(r"^enum nl80211_tx_power_setting \{[\s\S]*?^\};", nl, re.M)[0] + "\n"
constants += re.search(r"^#define MBM_TO_DBM\([^\n]+", ieee, re.M)[0] + "\n"
for name in ("DOT11_MAX_DEFAULT_KEYS",
             "WLAN_CIPHER_SUITE_WEP40", "WLAN_CIPHER_SUITE_WEP104",
             "WLAN_CIPHER_SUITE_TKIP", "WLAN_CIPHER_SUITE_CCMP", "RADIO_SW_DISABLE",
             "TXPWR_OVERRIDE"):
    constants += macro(name)
index = re.search(r"^enum p2p_bss_type \{[\s\S]*?^\};",
                  files["wland_p2p.h"], re.M)
assert index
constants += index[0] + "\n"
status = re.search(r"^enum wland_vif_status \{[\s\S]*?^\};",
                   files["wland_cfg80211.h"], re.M)
assert status
constants += status[0] + "\n"
constants += re.search(r"^enum wland_mode \{[\s\S]*?^\};",
                       files["wland_cfg80211.h"], re.M)[0] + "\n"
stop = re.search(r"^\s*WID_STOP_AP_MAC1\s*=\s*([^,\n]+),", files["wland_wid.h"], re.M)
assert stop
constants += "enum { WID_STOP_AP_MAC1 = " + stop[1] + " };\n"
advertised = re.search(r"^static const u32 __wl_cipher_suites\[\] = \{[\s\S]*?^\};",
                       files["wland_cfg80211.c"], re.M)[0]
assert re.findall(r"WLAN_CIPHER_SUITE_\w+", advertised) == [
    "WLAN_CIPHER_SUITE_WEP40", "WLAN_CIPHER_SUITE_WEP104", "WLAN_CIPHER_SUITE_TKIP",
    "WLAN_CIPHER_SUITE_CCMP"]
assert "wiphy->cipher_suites = __wl_cipher_suites;" in files["wland_cfg80211.c"]
assert "wiphy->n_cipher_suites = ARRAY_SIZE(__wl_cipher_suites);" in files["wland_cfg80211.c"]
power = definition("wland_cfg80211.c", "wland_cfg80211_get_tx_power")
assert '*dbm);' not in power, "An error-path debug log reads an unset output"

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
#define ETH_ALEN 6
#define KERNEL_VERSION(a,b,c) (((a) << 16) | ((b) << 8) | (c))
#define LINUX_VERSION_CODE KERNEL_VERSION(6,12,112)
#define WLAND_DBG(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
/* CONSTANTS */
struct wiphy { int unused; };
struct key_params { const u8 *key; const u8 *seq; int key_len; int seq_len; u32 cipher; };
struct wireless_dev { enum nl80211_iftype iftype; };
struct wland_cfg80211_vif { struct wireless_dev wdev; unsigned long sme_state; bool tx_gtk_valid; u8 tx_gtk_index; enum wland_mode mode; };
struct vif_params { int unused; };
static char rdawlan_firmware_path[5];
struct wland_if;
struct net_device { struct wireless_dev *ieee80211_ptr; struct wland_if *priv; };
struct wland_if { struct wland_cfg80211_vif *vif; int bssidx; u8 mac_addr[ETH_ALEN]; };
struct wland_cfg80211_conf { int tx_power; };
struct wland_cfg80211_info { struct wland_cfg80211_conf *conf; struct net_device *ndev; };
static struct wland_cfg80211_info config;
static struct wland_cfg80211_info *wiphy_to_cfg(struct wiphy *wiphy) { (void)wiphy; return &config; }
static struct net_device *cfg_to_ndev(struct wland_cfg80211_info *cfg) { return cfg->ndev; }
/* Conversion is immaterial when the real transport reports unsupported. */
static u8 wland_mw_to_qdbm(u16 power) { (void)power; return 12; }
static u16 wland_qdbm_to_mw(u8 power) { (void)power; assert(false); return 0; }
static bool ready;
static int firmware_calls, callbacks, reply_status;
static u8 payload[ETH_ALEN];
static unsigned long state_at_request;
static void *netdev_priv(struct net_device *ndev) { return ndev->priv; }
static bool wland_check_vif_up(struct wland_cfg80211_vif *vif) { (void)vif; return ready; }
static bool is_valid_ether_addr(const u8 *address) {
    bool any = false;
    for (int i = 0; i < ETH_ALEN; i++) any |= address[i] != 0;
    return any && !(address[0] & 1);
}
static void set_bit(unsigned bit, unsigned long *state) { *state |= 1ul << bit; }
static void clear_bit(unsigned bit, unsigned long *state) { *state &= ~(1ul << bit); }
static int wland_fil_set_cmd_data(struct wland_if *ifp, u32 wid, const void *data, u16 size) {
    assert(wid == WID_STOP_AP_MAC1 && size == ETH_ALEN);
    firmware_calls++; memcpy(payload, data, size); state_at_request = ifp->vif->sme_state;
    return reply_status;
}
static void key_callback(void *cookie, struct key_params *params) {
    (void)cookie; (void)params; callbacks++;
}
/* FUNCTIONS */
/* ADVERTISED */
static struct wiphy phy;
static struct wland_cfg80211_vif vif;
static struct wland_if interface = {&vif, 0, {2,3,4,5,6,7}};
static struct net_device netdev = {&vif.wdev, &interface};
static struct wland_cfg80211_conf settings;
static void reset(enum nl80211_iftype role) {
    ready = true; firmware_calls = callbacks = 0; reply_status = 0;
    interface.bssidx = P2PAPI_BSSCFG_DEVICE; vif.wdev.iftype = role;
    vif.tx_gtk_valid = false; vif.tx_gtk_index = 0;
    netdev.ieee80211_ptr = &vif.wdev;
    config.conf = &settings; config.ndev = &netdev; settings.tx_power = 0x1234;
    const u8 address[] = {2,3,4,5,6,7}; memcpy(interface.mac_addr, address, ETH_ALEN);
    vif.sme_state = (1ul << VIF_STATUS_AP_CREATED) | (1ul << VIF_STATUS_READY);
    memset(payload, 0xa5, sizeof(payload)); state_at_request = 0;
}
static void unsupported_keys(void) {
    for (int role = NL80211_IFTYPE_UNSPECIFIED; role < NUM_NL80211_IFTYPES; role++) {
        for (unsigned index = 0; index <= 255; index++) for (int pairwise = 0; pairwise < 2; pairwise++) {
            reset(role); const unsigned long original = vif.sme_state;
            int expected = index < DOT11_MAX_DEFAULT_KEYS ? -EOPNOTSUPP : -EINVAL;
            assert(wland_cfg80211_del_key(&phy, &netdev, -1, index, pairwise, NULL) == expected);
            assert(wland_cfg80211_get_key(&phy, &netdev, -1, index, pairwise, NULL, NULL, key_callback) == expected);
            for (int flags = 0; flags < 4; flags++)
                assert(wland_cfg80211_config_default_key(&phy, &netdev, -1, index, flags & 1, flags & 2) == expected);
            assert(!firmware_calls && !callbacks && vif.sme_state == original);
        }
    }
    reset(NL80211_IFTYPE_STATION); ready = false;
    assert(wland_cfg80211_del_key(&phy, &netdev, -1, 0, false, NULL) == -EIO);
    assert(wland_cfg80211_get_key(&phy, &netdev, -1, 0, false, NULL, NULL, key_callback) == -EIO);
    assert(wland_cfg80211_config_default_key(&phy, &netdev, -1, 0, true, true) == -EIO);
    ready = true;
    reset(NL80211_IFTYPE_AP); vif.tx_gtk_valid = true; vif.tx_gtk_index = 2;
    assert(wland_cfg80211_config_default_key(&phy, &netdev, -1, 2, false, true) == 0);
    assert(wland_cfg80211_config_default_key(&phy, &netdev, -1, 1, false, true) == -EOPNOTSUPP);
    assert(wland_cfg80211_config_default_key(&phy, &netdev, -1, 2, true, true) == -EOPNOTSUPP);
    vif.tx_gtk_valid = false;
    assert(wland_cfg80211_config_default_key(&phy, &netdev, -1, 2, false, true) == -EOPNOTSUPP);
    reset(NL80211_IFTYPE_STATION);
    assert(wland_cfg80211_get_key(&phy, &netdev, -1, 0, false, NULL, NULL, NULL) == -EINVAL);
    assert(wland_cfg80211_del_key(&phy, &netdev, 1, 0, false, NULL) == -EOPNOTSUPP);
    assert(wland_cfg80211_get_key(&phy, &netdev, 1, 0, false, NULL, NULL, key_callback) == -EOPNOTSUPP);
    assert(wland_cfg80211_config_default_key(&phy, &netdev, 1, 0, true, true) == -EOPNOTSUPP);
    assert(!firmware_calls && !callbacks);
}
static void named_iovars(void) {
    char *names[] = {"wsec", "qtxpower", "wsec_key", "set_key_primary", "unknown", NULL};
    const u16 lengths[] = {0, 1, 4, 32, 65535};
    u8 data[32], original[32]; memset(data, 0xa5, sizeof(data)); memcpy(original, data, sizeof(data));
    for (unsigned n = 0; n < sizeof(names)/sizeof(names[0]); n++)
        for (unsigned length = 0; length < sizeof(lengths)/sizeof(lengths[0]); length++) {
            assert(wland_fil_iovar_data_set(&interface, names[n], data, lengths[length]) == -EOPNOTSUPP);
            assert(wland_fil_iovar_data_get(&interface, names[n], data, lengths[length]) == -EOPNOTSUPP);
            assert(!memcmp(data, original, sizeof(data)));
            assert(wland_fil_iovar_data_set(NULL, names[n], NULL, lengths[length]) == -EOPNOTSUPP);
            assert(wland_fil_iovar_data_get(NULL, names[n], NULL, lengths[length]) == -EOPNOTSUPP);
        }
    assert(!firmware_calls && !callbacks);
}
static void stop_ap(void) {
    const int results[] = {0, 6, -EIO, -ETIMEDOUT, -EPROTO};
    for (int role = NL80211_IFTYPE_UNSPECIFIED; role < NUM_NL80211_IFTYPES; role++) {
        for (int bssidx = -1; bssidx <= 3; bssidx++) {
            for (unsigned result = 0; result < sizeof(results)/sizeof(results[0]); result++) {
                reset(role); interface.bssidx = bssidx; reply_status = results[result];
                const unsigned long original = vif.sme_state;
                const bool supported = (role == NL80211_IFTYPE_AP || role == NL80211_IFTYPE_P2P_GO)
                                       && bssidx == P2PAPI_BSSCFG_DEVICE;
                int returned = wland_cfg80211_stop_ap(&phy, &netdev, 0);
                if (!supported) {
                    assert(returned == -EOPNOTSUPP && !firmware_calls && vif.sme_state == original);
                } else {
                    assert(firmware_calls == 1 && state_at_request == original);
                    assert(!memcmp(payload, interface.mac_addr, ETH_ALEN));
                    if (results[result] < 0) {
                        assert(returned == results[result] && vif.sme_state == original);
                    } else {
                        assert(!returned && vif.sme_state == ((original & ~(1ul << VIF_STATUS_AP_CREATED))
                                                              | (1ul << VIF_STATUS_AP_CREATING)));
                    }
                }
            }
        }
    }
    reset(NL80211_IFTYPE_AP); unsigned long original = vif.sme_state;
    assert(wland_cfg80211_stop_ap(&phy, &netdev, 1) == -EOPNOTSUPP && !firmware_calls);
    struct wireless_dev foreign = {NL80211_IFTYPE_STATION}; netdev.ieee80211_ptr = &foreign;
    assert(wland_cfg80211_stop_ap(&phy, &netdev, 0) == -EINVAL && !firmware_calls);
    netdev.ieee80211_ptr = &vif.wdev; ready = false;
    assert(wland_cfg80211_stop_ap(&phy, &netdev, 0) == -EIO && !firmware_calls);
    ready = true;
    const u8 invalid[][6] = {{0}, {1,2,3,4,5,6}, {255,255,255,255,255,255}};
    for (unsigned i = 0; i < sizeof(invalid)/sizeof(invalid[0]); i++) {
        memcpy(interface.mac_addr, invalid[i], ETH_ALEN);
        assert(wland_cfg80211_stop_ap(&phy, &netdev, 0) == -EINVAL && !firmware_calls);
        assert(vif.sme_state == original);
    }
}
static void tx_power(void) {
    reset(NL80211_IFTYPE_STATION);
    int output = 0x1234;
    assert(wland_cfg80211_get_tx_power(&phy, &vif.wdev, &output) == -EOPNOTSUPP);
    assert(output == 0x1234);
    for (int type = NL80211_TX_POWER_AUTOMATIC; type <= NL80211_TX_POWER_FIXED; type++) {
        assert(wland_cfg80211_set_tx_power(&phy, &vif.wdev, type, 2000) == -EOPNOTSUPP);
        assert(settings.tx_power == 0x1234);
    }
    ready = false;
    assert(wland_cfg80211_get_tx_power(&phy, &vif.wdev, &output) == -EIO && output == 0x1234);
    assert(wland_cfg80211_set_tx_power(&phy, &vif.wdev, NL80211_TX_POWER_FIXED, 2000) == -EIO);
    assert(settings.tx_power == 0x1234 && !firmware_calls);
}
static void change_iface(void) {
    const char *firmware[] = {"sta", "ap", "p2p"};
    for (unsigned f = 0; f < 3; f++) {
        for (int type = 0; type < NUM_NL80211_IFTYPES; type++) {
            reset(NL80211_IFTYPE_STATION); interface.bssidx = 0;
            vif.mode = WL_MODE_BSS;
            strcpy(rdawlan_firmware_path, firmware[f]);
            bool supported = (f == 0 && type == NL80211_IFTYPE_STATION) ||
                             (f == 1 && type == NL80211_IFTYPE_AP);
            int result = wland_cfg80211_change_virtual_iface(&phy, &netdev, type, NULL);
            assert(result == (supported ? 0 : -EOPNOTSUPP));
            assert((int)vif.wdev.iftype == (supported ? type : NL80211_IFTYPE_STATION));
            assert(vif.mode == (supported && f == 1 ? WL_MODE_AP : WL_MODE_BSS));
            assert(!firmware_calls);
        }
    }
    interface.bssidx = 1; strcpy(rdawlan_firmware_path, "sta");
    assert(wland_cfg80211_change_virtual_iface(&phy, &netdev, NL80211_IFTYPE_STATION, NULL) == -EOPNOTSUPP);
}
int main(void) {
    unsupported_keys(); named_iovars(); stop_ap(); tx_power(); change_iface();
    assert(sizeof(__wl_cipher_suites)/sizeof(__wl_cipher_suites[0]) == 4);
    puts("RDA_OPERATIONS_PASS: actual unsupported callbacks/iovars, output preservation, AP-stop payload/reply ordering and cipher declarations");
}
'''
code = code.replace("/* CONSTANTS */", constants)
functions = [definition("wland_cmds.c", name) for name in (
    "wland_fil_iovar_data_set", "wland_fil_iovar_data_get")]
functions += [definition("wland_cfg80211.c", name) for name in (
    "wland_cfg80211_del_key", "wland_cfg80211_get_key", "wland_cfg80211_config_default_key",
    "wland_cfg80211_stop_ap", "wland_cfg80211_set_tx_power", "wland_cfg80211_get_tx_power",
    "wland_cfg80211_change_virtual_iface")]
code = code.replace("/* FUNCTIONS */", "\n".join(functions))
code = code.replace("/* ADVERTISED */", advertised)
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "operations.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-but-set-variable",
                    str(temp / "operations.c"), "-o", str(temp / "operations")], check=True)
    subprocess.run([str(temp / "operations")], check=True)
print("RDA operation sanitizer pass; unsupported requests remain unsupported, no firmware/radio acceptance")
