#!/usr/bin/env python3
"""Execute the real RDA band updater against typed firmware replies."""
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
source = (root / "wland_cfg80211.c").read_text()
spans = function_spans(source, "wland_update_wiphybands")
assert len(spans) == 1
start, _, end = spans[0]
body = source[start:end]
assert "wland_fil_iovar_" not in body
assert "wiphy_apply_custom_regulatory" not in body
header = (root / "wland_wid.h").read_text()
constants = ""
for name in ("WID_11N_ENABLE", "WID_11N_SHORT_GI_ENABLE"):
    value = re.search(r"\b" + name + r"\s*=\s*(0x[0-9A-Fa-f]+)", header)[1]
    constants += f"#define {name} {value}\n"

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef int32_t s32;
#define NL80211_BAND_2GHZ 0
#define IEEE80211_HT_CAP_SUP_WIDTH_20_40 2
#define IEEE80211_HT_CAP_SGI_20 32
#define IEEE80211_HT_CAP_SGI_40 64
#define IEEE80211_HT_MAX_AMPDU_64K 3
#define IEEE80211_HT_MPDU_DENSITY_16 7
/* CONSTANTS */
struct ieee80211_sta_ht_cap {
    bool ht_supported;
    unsigned cap, ampdu_factor, ampdu_density;
    struct { u8 rx_mask[10]; } mcs;
};
struct ieee80211_supported_band { struct ieee80211_sta_ht_cap ht_cap; };
static struct ieee80211_supported_band __wl_band_2ghz;
struct wiphy { struct ieee80211_supported_band *bands[2]; };
struct wland_if { int unused; };
struct wland_cfg80211_info { int unused; };
static struct wiphy phy;
static struct wland_if interface;
static struct wland_cfg80211_info cfg;
static int queries, replies[2];
static u8 values[2];
static void *cfg_to_ndev(struct wland_cfg80211_info *c) { assert(c == &cfg); return &interface; }
static void *netdev_priv(void *p) { assert(p == &interface); return p; }
static struct wiphy *cfg_to_wiphy(struct wland_cfg80211_info *c) { assert(c == &cfg); return &phy; }
static int wland_fil_get_cmd_data(struct wland_if *p, unsigned wid, void *data, unsigned len) {
    assert(p == &interface && len == 1 && queries < 2);
    assert(wid == (queries ? WID_11N_SHORT_GI_ENABLE : WID_11N_ENABLE));
    unsigned i = queries++;
    if (replies[i] > 0) memcpy(data, &values[i], 1);
    return replies[i];
}
/* REAL FUNCTION */
static void reset(void) {
    memset(&phy, 0, sizeof(phy)); memset(&__wl_band_2ghz, 0, sizeof(__wl_band_2ghz));
    queries = 0;
    replies[0] = replies[1] = values[0] = values[1] = 1;
}
int main(void) {
    for (int n = 0; n <= 1; n++) for (int sgi = 0; sgi <= 1; sgi++) {
        reset(); values[0] = n; values[1] = sgi;
        assert(!wland_update_wiphybands(&cfg, true));
        assert(queries == 1 + n && phy.bands[0] == &__wl_band_2ghz);
        struct ieee80211_sta_ht_cap *ht = &__wl_band_2ghz.ht_cap;
        assert(ht->ht_supported == n && ht->cap == (n ? 2u | (sgi ? 96u : 0u) : 0u));
        assert(ht->mcs.rx_mask[0] == (n ? 255 : 0));
        if (n) assert(ht->ampdu_factor == 3 && ht->ampdu_density == 7);
    }
    const int failures[] = {-EIO, -ETIMEDOUT, 0, 2};
    for (int q = 0; q < 2; q++) for (unsigned i = 0; i < 4; i++) {
        reset(); replies[q] = failures[i]; __wl_band_2ghz.ht_cap.cap = 1234;
        assert(wland_update_wiphybands(&cfg, true) == (failures[i] < 0 ? failures[i] : -EPROTO));
        assert(!phy.bands[0] && __wl_band_2ghz.ht_cap.cap == 1234);
    }
    for (int q = 0; q < 2; q++) {
        reset(); values[q] = 2;
        assert(wland_update_wiphybands(&cfg, true) == -EPROTO && !phy.bands[0]);
    }
    reset(); assert(!wland_update_wiphybands(&cfg, false));
    reset(); assert(!wland_update_wiphybands(&cfg, false));
    queries = 0; values[0] = 0;
    assert(!wland_update_wiphybands(&cfg, false) && !__wl_band_2ghz.ht_cap.cap);
    puts("RDA_TYPED_BAND_STATE_PASS: exact WIDs/lengths, invalid replies, transactional publication and retry");
}
'''
code = code.replace("/* CONSTANTS */", constants).replace("/* REAL FUNCTION */", body)
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "band.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", path / "band.c", "-o", path / "band"], check=True)
    subprocess.run([path / "band"], check=True)
