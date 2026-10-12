#!/usr/bin/env python3
"""Sanitize actual RDA NETINFO parsing and scan-handler IE ownership."""
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
    "wland_cfg80211.c", "wland_cfg80211.h", "wland_dev.h", "wland_rx.c", "wland_wid.h")}
vendor = (args.source / "include/80211.h").read_text()
linux = (args.linux / "include/linux/ieee80211.h").read_text()


def definition(name):
    text = files["wland_cfg80211.c"]
    if name == "wland_alloc_bss":
        begin = "static struct wland_bss_info_le *wland_alloc_bss("
        after = "\nstatic void wland_free_bss("
        assert text.count(begin) == text.count(after) == 1
        start = text.index(begin)
        return text[start:text.index(after, start)]
    spans = function_spans(text, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return text[start:end]


constants = ""
constants += re.search(r"^#define\s+MAKE_WORD16\([^\n]+", files["wland_dev.h"], re.M)[0] + "\n"
for name in ("MAC_HDR_LEN", "TIME_STAMP_LEN", "BEACON_INTERVAL_LEN", "CAP_INFO_LEN",
             "MAX_RATES", "MCSSET_LEN", "TLV_OUI_LEN", "WPA_OUI", "WME_OUI_TYPE",
             "IEEE80211_HT_MCS_MASK_LEN"):
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)",
                      "\n".join(files.values()) + vendor + linux, re.M)
    assert match, name
    constants += "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"
for name in ("BEACON", "PROBE_RSP", "WID_NETWORK_INFO",
             "WLAN_EID_SSID", "WLAN_EID_SUPP_RATES", "WLAN_EID_EXT_SUPP_RATES",
             "WLAN_EID_DS_PARAMS", "WLAN_EID_TIM", "WLAN_EID_HT_CAPABILITY", "WLAN_EID_VENDOR_SPECIFIC"):
    match = re.search(r"\b" + name + r"\s*=\s*(0x[0-9a-fA-F]+|[0-9]+)\s*,",
                      "\n".join(files.values()) + vendor + linux)
    assert match, name
    constants += "#define " + name + " " + match[1] + "\n"
structures = re.search(r"^struct wland_bss_info_le \{[\s\S]*?^\};", files["wland_dev.h"], re.M)[0]
for name in ("ieee80211_mcs_info", "ieee80211_ht_cap"):
    structures += "\n" + re.search(r"^struct " + name + r" \{[\s\S]*?^\} __packed;", linux, re.M)[0]
handler = definition("wland_notify_escan_handler")
assert "wland_parse_network_info(&bss_info_le, data, e->datalen)" in handler
assert "kfree(bss_info_le.ie);" in handler
rx = files["wland_rx.c"]
start, _, end = function_spans(rx, "wland_handle_async_info")[0]
rx = rx[start:end]
assert rx.index("event_packet->datalen < 8") < rx.index("wid_id = p_buffer[4]")
assert rx.index("wland_port_network_frame_length(") < rx.index("sub_type = p_frame[0]")
rx_entry = rx[rx.index("\tif (!event_packet || !p_buffer)"):rx.index("\n\tswitch (wid_id)")]

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef int8_t s8; typedef uint16_t u16; typedef int16_t s16;
typedef uint32_t u32; typedef int32_t s32; typedef uint16_t __le16; typedef uint32_t __le32;
#define __packed __attribute__((packed))
#define ETH_ALEN 6
#define GFP_KERNEL 0
#define min_t(type, a, b) ((type)(a) < (type)(b) ? (type)(a) : (type)(b))
#define max(a, b) ((a) > (b) ? (a) : (b))
#define BIT(value) (1ul << (value))
#define WRITE_ONCE(target, value) ((target) = (value))
#define ERR_PTR(value) ((void *)(intptr_t)(value))
#define PTR_ERR(value) ((int)(intptr_t)(value))
#define IS_ERR(value) ((uintptr_t)(value) >= (uintptr_t)-4095)
enum { CFG80211, RX, TRACE, DEBUG, ERROR, INFO, STATUS_SUCCESS = 0, SITE_SURVEY_ALL_CH = 255,
       P2PAPI_BSSCFG_PRIMARY = 0, NL80211_IFTYPE_ADHOC = 1, CAPABILITY_IBSS = 2,
       SCAN_STATUS_BUSY = 0, SCAN_STATE_IDLE = 0 };
#define WLAND_P2P_SUPPORT
static void debug_log(int area, int level, const char *format, ...) {
    char text[1024]; va_list args; va_start(args, format);
    assert(vsnprintf(text, sizeof(text), format, args) >= 0); va_end(args);
}
#define WLAND_DBG(...) debug_log(__VA_ARGS__)
#define WLAND_ERR(...) debug_log(0, 0, __VA_ARGS__)
/* CONSTANTS */
struct list_head { struct list_head *next, *prev; };
/* STRUCTURES */
static void list_init(struct list_head *list) { list->next = list->prev = list; }
static void list_add_tail(struct list_head *item, struct list_head *head) {
    item->prev = head->prev; item->next = head; head->prev->next = item; head->prev = item;
}
#define list_for_each_entry(pos, head, member) \
    for (struct list_head *node = (head)->next; node != (head) && \
         (((pos) = (void *)((char *)node - offsetof(__typeof__(*(pos)), member))), 1); node = node->next)
static int allocations, allocation_calls, fail_call;
static void *live[32];
static void *kmemdup(const void *data, size_t length, int flags) {
    allocation_calls++; if (allocation_calls == fail_call) return NULL;
    void *copy = malloc(length); assert(copy); memcpy(copy, data, length);
    unsigned index; for (index = 0; index < 32 && live[index]; index++);
    assert(index < 32); live[index] = copy; allocations++; return copy;
}
static void kfree(void *data) {
    if (!data) return;
    unsigned index; for (index = 0; index < 32 && live[index] != data; index++);
    assert(index < 32); live[index] = NULL; allocations--; free(data);
}
/* GUARD */
/* PARSER */
struct wland_if;
struct wland_cfg80211_vif { struct wland_if *ifp; };
struct cfg80211_scan_request { int unused; };
struct wland_pub { int country_code; };
struct wland_cfg80211_info {
    struct cfg80211_scan_request *scan_request;
    struct { struct wland_if *ifp; int escan_state; } scan_info;
    struct wland_pub *pub;
    int scan_result_lock, scan_timeout, scan_report_work, scannum;
    unsigned long scan_status;
    bool ctrl_scan_wait;
    struct { unsigned count; u16 beacon_period; } scan_results;
    struct list_head scan_result_list;
};
struct wland_private { struct wland_cfg80211_info *config; };
struct wland_if { struct wland_private *drvr; struct wland_cfg80211_vif *vif; int bssidx; u8 mac_addr[6]; };
struct wland_event_msg { u32 status, datalen; };
struct wiphy { unsigned long interface_modes; };
static struct wiphy phy;
static struct wland_pub pub = {SITE_SURVEY_ALL_CH};
static struct wland_cfg80211_info config;
static struct wland_private driver = {&config};
static struct wland_if interface;
static struct wland_cfg80211_vif vif = {&interface};
static struct wland_if interface = {&driver, &vif, P2PAPI_BSSCFG_PRIMARY, {0}};
static struct cfg80211_scan_request request;
static unsigned long jiffies = 1234;
static int lock_depth, wakeups, informs;
static bool ready = true, p2p_skip;
static bool ether_addr_equal(const u8 *a, const u8 *b) { return !memcmp(a, b, ETH_ALEN); }
static bool wland_check_vif_up(struct wland_cfg80211_vif *value) { assert(value == &vif); return ready; }
static bool wland_p2p_scan_finding_common_channel(struct wland_cfg80211_info *cfg,
                                                struct wland_bss_info_le *bi) { return bi && p2p_skip; }
static struct wiphy *cfg_to_wiphy(struct wland_cfg80211_info *cfg) { return &phy; }
static void mutex_lock(int *lock) { assert(!lock_depth); lock_depth++; }
static void mutex_unlock(int *lock) { assert(lock_depth == 1); lock_depth--; }
static bool timer_pending(int *timer) { return !!*timer; }
static void del_timer_sync(int *timer) { *timer = 0; }
static void wland_wait_event_scancmp_wakeup(struct wland_cfg80211_info *cfg) {
    assert(!cfg->ctrl_scan_wait); wakeups++;
}
static void wland_inform_bss(struct wland_cfg80211_info *cfg) { informs++; }
static bool test_bit(int bit, unsigned long *value) { return *value & BIT(bit); }
static void clear_bit(int bit, unsigned long *value) { *value &= ~BIT(bit); }
static void schedule_work(int *work) { (*work)++; }
/* ALLOC */
/* COMPARE */
/* HANDLER */
/* Actual RX entry checks; the later dispatch/association branches are excluded. */
static int rx_network_entry(struct wland_event_msg *event_packet, u8 *p_buffer) {
    s32 ret = 0; u16 wid_id; size_t network_frame_length;
    /* RX ENTRY */
    return 0;
}
static void put16(u8 *data, unsigned value) { data[0] = value; data[1] = value >> 8; }
static size_t append(u8 *data, size_t position, u8 id, const u8 *value, size_t length) {
    assert(length <= 255); data[position++] = id; data[position++] = length;
    memcpy(data + position, value, length); return position + length;
}
static size_t packet(u8 *data, unsigned ssid_length) {
    memset(data, 0, 1024); data[0] = 'N'; data[8] = (u8)-42; put16(data + 4, WID_NETWORK_INFO);
    u8 *frame = data + 9; frame[0] = BEACON; memcpy(frame + 16, "ABCDEF", 6);
    put16(frame + 32, 100); put16(frame + 34, 0x0411);
    u8 ssid[32], rates[] = {0x82, 0x84, 0x8b, 0x96}, extended[] = {12, 18, 24};
    u8 channel = 6, tim[] = {0, 3, 0, 0}, ht[sizeof(struct ieee80211_ht_cap)] = {0};
    const u8 wmm[] = {0, 0x50, 0xf2, WME_OUI_TYPE}; memset(ssid, 'S', sizeof(ssid));
    size_t end = 45;
    end = append(data, end, WLAN_EID_SSID, ssid, ssid_length);
    end = append(data, end, WLAN_EID_SUPP_RATES, rates, sizeof(rates));
    end = append(data, end, WLAN_EID_DS_PARAMS, &channel, 1);
    end = append(data, end, WLAN_EID_TIM, tim, sizeof(tim));
    end = append(data, end, WLAN_EID_EXT_SUPP_RATES, extended, sizeof(extended));
    end = append(data, end, WLAN_EID_HT_CAPABILITY, ht, sizeof(ht));
    end = append(data, end, WLAN_EID_VENDOR_SPECIFIC, wmm, sizeof(wmm));
    put16(data + 2, end); put16(data + 6, end - 8); return end;
}
static void reject(const u8 *data, size_t length) {
    u8 *exact = malloc(length ? length : 1); assert(exact); if (length) memcpy(exact, data, length);
    struct wland_bss_info_le output, before; memset(&output, 0xa5, sizeof(output)); before = output;
    int calls = allocation_calls;
    assert(wland_parse_network_info(&output, exact, length) < 0);
    assert(!memcmp(&before, &output, sizeof(output)) && calls == allocation_calls);
    if (length) assert(!memcmp(exact, data, length));
    free(exact);
}
static void parse_valid(void) {
    u8 data[1024]; const u8 rates[] = {0x82, 0x84, 0x8b, 0x96, 12, 18, 24};
    for (unsigned length = 0; length <= 32; length++) {
        size_t size = packet(data, length); struct wland_bss_info_le output = {0};
        u8 *exact = malloc(size); assert(exact); memcpy(exact, data, size);
        assert(!wland_parse_network_info(&output, exact, size));
        assert(output.SSID_len == length && !memcmp(output.SSID, data + 47, length));
        assert(output.ctl_ch == 6 && output.RSSI == -42 && output.beacon_period == 100);
        assert(output.capability == 0x0411 && output.dtim_period == 3 && output.n_enable && output.wmm_enable);
        assert(output.rateset.count == sizeof(rates) && !memcmp(output.rateset.rates, rates, sizeof(rates)));
        assert(!memcmp(output.BSSID, "ABCDEF", 6) && output.ie_length == size - 45);
        assert(!memcmp(output.ie, data + 45, output.ie_length) && !memcmp(exact, data, size));
        kfree(output.ie); free(exact); assert(!allocations);
        data[9] = PROBE_RSP; assert(!wland_parse_network_info(&output, data, size)); kfree(output.ie);
        assert(!wland_parse_network_info(&output, data, size + 4)); kfree(output.ie); /* transport padding */
    }
    size_t size = packet(data, 32); u8 rates_long[255];
    for (unsigned i = 0; i < sizeof(rates_long); i++) rates_long[i] = i + 1;
    size = append(data, 45, WLAN_EID_SUPP_RATES, rates_long, sizeof(rates_long));
    size = append(data, size, WLAN_EID_EXT_SUPP_RATES, rates_long, sizeof(rates_long));
    put16(data + 2, size); put16(data + 6, size - 8);
    struct wland_bss_info_le output = {0}; assert(!wland_parse_network_info(&output, data, size));
    assert(output.rateset.count == MAX_RATES && !memcmp(output.rateset.rates, rates_long, MAX_RATES));
    kfree(output.ie); assert(!allocations);
}
static void parse_invalid(void) {
    u8 data[1024], changed[1024]; size_t size = packet(data, 32);
    for (size_t cut = 0; cut < size; cut++) reject(data, cut);
    for (size_t cut = 0; cut < size; cut++) {
        u8 *exact = malloc(cut ? cut : 1); assert(exact); memcpy(exact, data, cut);
        struct wland_event_msg event = {STATUS_SUCCESS, cut};
        assert(rx_network_entry(&event, exact) < 0); free(exact);
    }
    struct wland_event_msg event = {STATUS_SUCCESS, size};
    assert(!rx_network_entry(&event, data));
    assert(rx_network_entry(NULL, data) == -EINVAL && rx_network_entry(&event, NULL) == -EINVAL);
    const unsigned bad_lengths[] = {0, 1, 7, 65535};
    for (unsigned i = 0; i < sizeof(bad_lengths)/sizeof(bad_lengths[0]); i++) {
        memcpy(changed, data, size); put16(changed + 2, bad_lengths[i]);
        assert(rx_network_entry(&event, changed) < 0);
        memcpy(changed, data, size); put16(changed + 6, bad_lengths[i]);
        assert(rx_network_entry(&event, changed) < 0);
    }
    size_t frame_size = 987; assert(wland_port_network_frame_length(NULL, size, &frame_size) == -EINVAL);
    assert(wland_port_network_frame_length(data, size, NULL) == -EINVAL && frame_size == 987);
    struct wland_bss_info_le output; assert(wland_parse_network_info(NULL, data, size) == -EINVAL);
    assert(wland_parse_network_info(&output, NULL, size) == -EINVAL);
    const unsigned fields[] = {2, 6};
    for (unsigned field = 0; field < 2; field++) for (unsigned value = 0; value <= 65535; value++) {
        memcpy(changed, data, size); put16(changed + fields[field], value);
        int calls = allocation_calls;
        memset(&output, 0xa5, sizeof(output)); struct wland_bss_info_le before = output;
        int result = wland_parse_network_info(&output, changed, size);
        if (!result) kfree(output.ie);
        else assert(!memcmp(&before, &output, sizeof(output)) && calls == allocation_calls);
    }
    memcpy(changed, data, size); changed[0] = 'R'; reject(changed, size);
    memcpy(changed, data, size); changed[4]++; reject(changed, size);
    memcpy(changed, data, size); changed[9] = 0; reject(changed, size);
    memcpy(changed, data, size); changed[10] = 1; reject(changed, size);
    for (size_t element = 45; element < size; element += data[element + 1] + 2) {
        memcpy(changed, data, size); changed[element + 1] = 255; reject(changed, size);
        size_t partial = element + 1; memcpy(changed, data, partial);
        put16(changed + 2, partial); put16(changed + 6, partial - 8); reject(changed, partial);
    }
    memcpy(changed, data, size); changed[46] = 33; reject(changed, size);
    const u8 short_value[25] = {0};
    const unsigned typed_ids[] = {WLAN_EID_DS_PARAMS, WLAN_EID_TIM, WLAN_EID_HT_CAPABILITY};
    const unsigned typed_lengths[] = {0, 3, 25};
    for (unsigned i = 0; i < 3; i++) {
        memcpy(changed, data, 45);
        size_t malformed = append(changed, 45, typed_ids[i], short_value, typed_lengths[i]);
        put16(changed + 2, malformed); put16(changed + 6, malformed - 8); reject(changed, malformed);
    }
    const u8 ssid = 'x'; size_t duplicate = append(data, size, WLAN_EID_SSID, &ssid, 1);
    put16(data + 2, duplicate); put16(data + 6, duplicate - 8); reject(data, duplicate);
    size = packet(data, 32); memset(&output, 0xa5, sizeof(output));
    struct wland_bss_info_le before = output; fail_call = allocation_calls + 1;
    assert(wland_parse_network_info(&output, data, size) == -ENOMEM);
    assert(!memcmp(&output, &before, sizeof(output)) && !allocations); fail_call = 0;
}
static void reset_handler(void) {
    assert(!allocations && !lock_depth); memset(&config, 0, sizeof(config));
    config.scan_request = &request; config.scan_info.ifp = &interface; config.pub = &pub;
    config.scan_timeout = 1; config.scan_status = BIT(SCAN_STATUS_BUSY);
    vif.ifp = &interface;
    interface.bssidx = P2PAPI_BSSCFG_PRIMARY;
    list_init(&config.scan_result_list); ready = true; p2p_skip = false;
    pub.country_code = SITE_SURVEY_ALL_CH; phy.interface_modes = 0; informs = wakeups = 0;
}
static void discard_list(void) {
    while (config.scan_result_list.next != &config.scan_result_list) {
        struct list_head *node = config.scan_result_list.next;
        config.scan_result_list.next = node->next; node->next->prev = &config.scan_result_list;
        struct wland_bss_info_le *bss = (void *)((char *)node - offsetof(struct wland_bss_info_le, list));
        kfree(bss->ie); kfree(bss);
    }
    assert(!allocations);
}
static void handler_paths(void) {
    u8 data[1024]; size_t size = packet(data, 32);
    struct wland_event_msg event = {STATUS_SUCCESS, size};
    reset_handler(); assert(wland_notify_escan_handler(NULL, &event, data) == -EINVAL);
    assert(wland_notify_escan_handler(&interface, NULL, data) == -EINVAL);
    config.scan_info.ifp = NULL; assert(wland_notify_escan_handler(&interface, &event, data) == -EINVAL);
    reset_handler(); vif.ifp = NULL;
    assert(wland_notify_escan_handler(&interface, &event, data) == -EINVAL && !allocations);
    reset_handler(); assert(wland_notify_escan_handler(&interface, &event, NULL) == -EINVAL && !allocations);
    ready = false; assert(!wland_notify_escan_handler(&interface, &event, data) && !allocations);
    reset_handler(); event.datalen = 8;
    assert(wland_notify_escan_handler(&interface, &event, data) == -EMSGSIZE && !allocations);
    event.datalen = size;
    for (int reason = 0; reason < 7; reason++) {
        reset_handler(); size = packet(data, reason == 1 ? 0 : 32); event.datalen = size;
        if (reason == 0) { /* no DS channel */
            for (size_t pos = 45; pos < size; pos += data[pos + 1] + 2)
                if (data[pos] == WLAN_EID_DS_PARAMS) data[pos + 2] = 0;
        } else if (reason == 2) {
            pub.country_code = 0;
            for (size_t pos = 45; pos < size; pos += data[pos + 1] + 2)
                if (data[pos] == WLAN_EID_DS_PARAMS) data[pos + 2] = 14;
        } else if (reason == 3) p2p_skip = true;
        else if (reason == 4) config.scan_request = NULL;
        else if (reason == 5) put16(data + 43, CAPABILITY_IBSS);
        else if (reason == 6) {
            interface.bssidx = 1; data[9] = PROBE_RSP; memcpy(data + 13, "FEDCBA", ETH_ALEN);
        }
        assert(!wland_notify_escan_handler(&interface, &event, data));
        assert(!allocations && !config.scan_results.count && !lock_depth);
    }
    reset_handler(); size = packet(data, 32); event.datalen = size;
    fail_call = allocation_calls + 1;
    assert(wland_notify_escan_handler(&interface, &event, data) == -ENOMEM && !allocations);
    fail_call = allocation_calls + 2;
    assert(wland_notify_escan_handler(&interface, &event, data) == -ENOMEM && !allocations);
    fail_call = 0;
    assert(!wland_notify_escan_handler(&interface, &event, data) && allocations == 2);
    assert(config.scan_results.count == 1 && !lock_depth);
    for (unsigned i = 0; i < 20; i++) {
        data[8] = (u8)(-30 - i);
        assert(!wland_notify_escan_handler(&interface, &event, data) && allocations == 2);
        assert(config.scan_results.count == 1 && !lock_depth);
    }
    struct wland_bss_info_le *bss = (void *)((char *)config.scan_result_list.next - offsetof(struct wland_bss_info_le, list));
    assert(bss->SSID_len == 32 && bss->RSSI == -30 && bss->ie && bss->vif == &vif);
    discard_list(); reset_handler(); config.scannum = 1; config.ctrl_scan_wait = true;
    event.status = 1; assert(!wland_notify_escan_handler(&interface, &event, NULL));
    assert(wakeups == 1 && !config.ctrl_scan_wait && !allocations);
    config.scannum = 0; assert(!wland_notify_escan_handler(&interface, &event, NULL));
    assert(informs == 1 && !config.scan_timeout && !config.scan_status && config.scan_report_work == 1);
}
int main(void) {
    assert(sizeof(struct ieee80211_ht_cap) == 26);
    parse_valid(); parse_invalid(); handler_paths(); assert(!allocations && !lock_depth);
    puts("RDA_SCAN_RESULTS_PASS: bounded NETINFO/IE parsing, full SSIDs, rates and IE ownership");
}
'''
code = code.replace("/* CONSTANTS */", constants).replace("/* STRUCTURES */", structures)
code = code.replace("/* GUARD */", (root / "wland_port_scan.h").read_text())
code = code.replace("/* PARSER */", definition("wland_parse_network_info"))
code = code.replace("/* ALLOC */", definition("wland_alloc_bss"))
code = code.replace("/* COMPARE */", definition("wland_compare_update_same_bss"))
code = code.replace("/* HANDLER */", handler)
code = code.replace("/* RX ENTRY */", rx_entry)
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "test.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-sign-compare",
                    str(temp / "test.c"), "-o", str(temp / "test")], check=True)
    subprocess.run([str(temp / "test")], check=True)
