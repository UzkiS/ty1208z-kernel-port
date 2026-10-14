#!/usr/bin/env python3
"""Check actual RDA cfg80211 startup rollback without named-iovar setup."""
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
    "wland_cfg80211.c", "wland_cfg80211.h", "wland_cmds.c", "wland_defs.h", "wland_dev.h")}


def definition(filename, name):
    text = files[filename]
    spans = function_spans(text, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return text[start:end]


constants = re.search(r"^enum wland_vif_status \{[\s\S]*?^\};",
                       files["wland_cfg80211.h"], re.M)[0] + "\n"
constants += re.search(r"^enum USER_PS_MODE_T \{[\s\S]*?^\};", files["wland_dev.h"], re.M)[0] + "\n"
for name in ("WLAND_BEACON_TIMEOUT",
             "ROAM_TRIGGER_LEVEL", "ROAM_DELTA", "WLAND_BAND_ALL"):
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)",
                      "\n".join(files.values()), re.M)
    assert match, name
    constants += "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
typedef uint32_t __le32;
#define cpu_to_le32(value) ((u32)(value))
#define KERNEL_VERSION(a,b,c) (((a) << 16) | ((b) << 8) | (c))
#define LINUX_VERSION_CODE KERNEL_VERSION(6,12,112)
#define WLAND_DBG(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
/* CONSTANTS */
struct wiphy { int unused; };
struct wireless_dev { struct wiphy *wiphy; int iftype; };
struct wland_cfg80211_vif { unsigned long sme_state; };
struct wland_if { struct wland_cfg80211_vif *vif; };
struct wland_cfg80211_info { int usr_sync; bool dongle_up, pwr_save, roam_on; };
struct net_device {
    struct wireless_dev *ieee80211_ptr;
    struct wland_if *priv;
    struct wland_cfg80211_info *config;
};
static struct wiphy phy;
static struct wireless_dev wireless = {&phy, 0};
static struct wland_cfg80211_vif vif;
static struct wland_if interface = {&vif};
static struct wland_cfg80211_info config;
static struct net_device netdev = {&wireless, &interface, &config};
static int lock_depth, locks, unlocks, stage, calls[3], replies[3];
static void *netdev_priv(struct net_device *ndev) { return ndev->priv; }
static struct wland_cfg80211_info *ndev_to_cfg(struct net_device *ndev) { return ndev->config; }
static void mutex_lock(int *mutex) { assert(mutex == &config.usr_sync && !lock_depth); lock_depth++; locks++; }
static void mutex_unlock(int *mutex) { assert(mutex == &config.usr_sync && lock_depth == 1); lock_depth--; unlocks++; }
static void set_bit(unsigned bit, unsigned long *state) { *state |= 1ul << bit; }
static void clear_bit(unsigned bit, unsigned long *state) { *state &= ~(1ul << bit); }
/* REAL NAMED TRANSPORT */
/* REAL LEGACY ROAM */
static int wland_cfg80211_change_virtual_iface(struct wiphy *wiphy, struct net_device *ndev,
                                               int type, void *params) {
    assert(lock_depth == 1 && stage == 0 && wiphy == &phy && ndev == &netdev
           && type == wireless.iftype && !params);
    assert(vif.sme_state & (1ul << VIF_STATUS_READY));
    stage++; calls[0]++; return replies[0];
}
static int wland_update_wiphybands(struct wland_cfg80211_info *cfg, bool notify) {
    assert(lock_depth == 1 && stage == 1 && cfg == &config && notify);
    stage++; calls[1]++; return replies[1];
}
/* REAL STARTUP */
static unsigned long reset(bool initially_ready) {
    memset(&config, 0, sizeof(config)); memset(calls, 0, sizeof(calls)); memset(replies, 0, sizeof(replies));
    vif.sme_state = (1ul << VIF_STATUS_CONNECTING) | (1ul << VIF_STATUS_AP_CREATED);
    if (initially_ready) vif.sme_state |= 1ul << VIF_STATUS_READY;
    lock_depth = locks = unlocks = stage = 0;
    return vif.sme_state & ~(1ul << VIF_STATUS_READY);
}
static void balanced(void) { assert(!lock_depth && locks == 1 && unlocks == 1); }
int main(void) {
    const int errors[] = {-EIO, -EOPNOTSUPP, -ETIMEDOUT, -EPROTO};
    for (int prior = 0; prior < 2; prior++) for (int failed = 0; failed < 2; failed++)
        for (unsigned e = 0; e < sizeof(errors)/sizeof(errors[0]); e++) {
            unsigned long untouched = reset(prior); replies[failed] = errors[e];
            assert(wland_cfg80211_up(&netdev) == errors[e]); balanced();
            assert(!config.dongle_up && vif.sme_state == untouched);
            for (int i = 0; i < 2; i++) assert(calls[i] == (i <= failed));
            /* A subsequent fully acknowledged fixture run may succeed. */
            memset(calls, 0, sizeof(calls)); memset(replies, 0, sizeof(replies));
            stage = locks = unlocks = 0;
            assert(!wland_cfg80211_up(&netdev)); balanced();
            assert(config.dongle_up && vif.sme_state == (untouched | (1ul << VIF_STATUS_READY)));
            assert(calls[0] == 1 && calls[1] == 1);
        }
    for (int prior = 0; prior < 2; prior++) {
        unsigned long untouched = reset(prior); config.dongle_up = true;
        assert(!wland_cfg80211_up(&netdev)); balanced();
        assert(config.dongle_up && vif.sme_state == (untouched | (1ul << VIF_STATUS_READY)));
        assert(!calls[0] && !calls[1]);
    }
    puts("RDA_STARTUP_ROLLBACK_PASS: actual up callback, interface/band failures, retry, fast path and balanced locking");
}
'''
code = code.replace("/* CONSTANTS */", constants)
code = code.replace("/* REAL STARTUP */", definition("wland_cfg80211.c", "wland_cfg80211_up"))
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "startup.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-but-set-variable",
                    str(temp / "startup.c"), "-o", str(temp / "startup")], check=True)
    subprocess.run([str(temp / "startup")], check=True)
print("Startup failure rollback passed; no named-iovar request remains in interface startup")
