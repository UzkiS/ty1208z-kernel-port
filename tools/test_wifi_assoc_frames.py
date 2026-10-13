#!/usr/bin/env python3
"""Sanitize actual STA/AP association-frame parsing and allocation ownership."""
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
source = (root / "wland_cfg80211.c").read_text()
headers = "\n".join((root / name).read_text() for name in (
    "wland_cfg80211.h", "wland_defs.h", "wland_dev.h"))
vendor = (args.source / "include/80211.h").read_text()
linux = (args.linux / "include/linux/ieee80211.h").read_text()
rx = (root / "wland_rx.c").read_text()
assert rx.count("ret = wland_get_assoc_ies_from_frame(") == 2
assert "if (!ret)\n\t\t\t\t\t\twland_analysis_assoc_ies(" in rx
start, _, end = function_spans(source, "wland_get_assoc_ies_from_frame")[0]
operation = source[start:end]
tlv_start = source.index("struct wland_tlv *wland_parse_tlvs(")
tlv_end = source.index("static struct wland_vs_tlv *wland_find_wpaie(", tlv_start)
tlv_helpers = source[tlv_start:tlv_end]
constants = ""
for name in ("MAC_HDR_LEN", "HT_CTRL_HDR_LEN", "MAC_HDR_ADDR2_OFFSET", "CAP_INFO_LEN",
             "LISTEN_INTERVAL_LEN", "STATUS_CODE_LEN", "AID_LEN", "BIT7", "TLV_HDR_LEN",
             "TLV_LEN_OFF", "TLV_BODY_OFF", "TLV_OUI_LEN", "WPA_OUI", "WME_OUI_TYPE",
             "IEEE80211_HT_MCS_MASK_LEN"):
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)", headers + vendor + linux, re.M)
    assert match, name
    constants += "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"
for name in ("ASSOC_REQ", "ASSOC_RSP", "WLAN_EID_SSID", "WLAN_EID_HT_CAPABILITY",
             "WLAN_EID_VENDOR_SPECIFIC"):
    match = re.search(r"\b" + name + r"\s*=\s*(0x[0-9a-fA-F]+|[0-9]+)\s*,", headers + vendor + linux)
    assert match, name
    constants += "#define " + name + " " + match[1] + "\n"
for name in ("IS_MGMT_HTC_PRESENT", "GET_MGMT_HDR_LEN"):
    match = re.search(r"^#define " + name + r"\([^\\\n]*(?:\\\n[^\\\n]*)*", vendor, re.M)
    assert match, name
    constants += match[0] + "\n"
structures = re.search(r"^struct wland_tlv \{[\s\S]*?^\};", headers, re.M)[0]
for name in ("ieee80211_mcs_info", "ieee80211_ht_cap"):
    structures += "\n" + re.search(r"^struct " + name + r" \{[\s\S]*?^\} __packed;", linux, re.M)[0]

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
typedef uint16_t __le16; typedef uint32_t __le32; typedef unsigned int uint;
#define __packed __attribute__((packed))
#define ETH_ALEN 6
#define GFP_ATOMIC 0
#define GFP_KERNEL 1
#define WLAND_DBG(...) ((void)0)
#define WLAND_DUMP(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
/* CONSTANTS */
/* STRUCTURES */
/* TLV HELPERS */
struct list_head { struct list_head *next, *prev; };
struct wland_sta_info {
    struct list_head list;
    u8 mac_addr[ETH_ALEN], *assoc_req_ie;
    s32 assoc_req_ie_len;
    bool wmm_enable, n_enable, connect;
    unsigned aid, tid_map, tid_num[8];
    unsigned long tid_jiffies[8];
};
struct wland_cfg80211_connect_info {
    struct list_head sta_info_list;
    int sta_info_lock;
    u8 *resp_ie;
    s32 resp_ie_len;
};
struct wland_cfg80211_vif { struct wland_cfg80211_connect_info conn_info; };
struct wland_if { struct wland_cfg80211_vif *vif; };
static struct wland_cfg80211_vif vif;
static struct wland_if interface = {&vif};
static int depth, calls, fail_call, allocations;
static void *live[32];
static unsigned long jiffies = 1234;
static void spin_lock_bh(int *lock) { assert(lock == &vif.conn_info.sta_info_lock && !depth); depth++; }
static void spin_unlock_bh(int *lock) { assert(lock == &vif.conn_info.sta_info_lock && depth == 1); depth--; }
static void atomic_set(unsigned *target, unsigned value) { *target = value; }
static void list_init(struct list_head *head) { head->next = head->prev = head; }
static void list_add_tail(struct list_head *item, struct list_head *head) {
    assert(depth == 1); item->prev = head->prev; item->next = head;
    head->prev->next = item; head->prev = item;
}
#define list_for_each_entry(pos, head, member) \
    for (struct list_head *node = (head)->next; node != (head) && \
         (((pos) = (void *)((char *)node - offsetof(__typeof__(*(pos)), member))), 1); node = node->next)
static void *allocate(size_t length, int flags) {
    assert(length && flags == GFP_ATOMIC);
    calls++; if (calls == fail_call) return NULL;
    void *copy = malloc(length); assert(copy);
    unsigned index; for (index = 0; index < 32 && live[index]; index++);
    assert(index < 32); live[index] = copy; allocations++; return copy;
}
static void *kmemdup(const void *data, size_t length, int flags) {
    void *copy = allocate(length, flags); if (copy) memcpy(copy, data, length); return copy;
}
static void *kzalloc(size_t length, int flags) {
    void *copy = allocate(length, flags); if (copy) memset(copy, 0, length); return copy;
}
static void kfree(void *data) {
    if (!data) return;
    unsigned index; for (index = 0; index < 32 && live[index] != data; index++);
    assert(index < 32); live[index] = NULL; allocations--; free(data);
}
/* ACTUAL OPERATION */
static unsigned stations(void) {
    unsigned count = 0; struct wland_sta_info *sta;
    list_for_each_entry(sta, &vif.conn_info.sta_info_list, list) count++;
    return count;
}
static struct wland_sta_info *first(void) {
    assert(stations() == 1);
    return (void *)((char *)vif.conn_info.sta_info_list.next - offsetof(struct wland_sta_info, list));
}
static void reset(void) {
    assert(!depth);
    struct wland_sta_info *sta;
    while (stations()) {
        sta = (void *)((char *)vif.conn_info.sta_info_list.next - offsetof(struct wland_sta_info, list));
        sta->list.next->prev = sta->list.prev; sta->list.prev->next = sta->list.next;
        kfree(sta->assoc_req_ie); kfree(sta);
    }
    kfree(vif.conn_info.resp_ie);
    assert(!allocations);
    memset(&vif, 0, sizeof(vif)); list_init(&vif.conn_info.sta_info_list);
    calls = fail_call = 0;
}
static size_t build(u8 *frame, u8 type, bool htc, const u8 *ies, size_t length) {
    size_t header = MAC_HDR_LEN + (htc ? HT_CTRL_HDR_LEN : 0);
    size_t fixed = type == ASSOC_REQ ? CAP_INFO_LEN + LISTEN_INTERVAL_LEN : CAP_INFO_LEN + STATUS_CODE_LEN + AID_LEN;
    memset(frame, 0, header + fixed + length); frame[0] = type; frame[1] = htc ? BIT7 : 0;
    const u8 mac[] = {2, 3, 4, 5, 6, 7}; memcpy(frame + MAC_HDR_ADDR2_OFFSET, mac, sizeof(mac));
    if (length) memcpy(frame + header + fixed, ies, length);
    return header + fixed + length;
}
int main(void) {
    list_init(&vif.conn_info.sta_info_list);
    u8 frame[512], rich[64] = {0, 3, 'a', 'p', '1', 221, 4, 0, 0x50, 0xf2, 2, 45, 26};
    const size_t rich_len = 39;
    for (unsigned type_index = 0; type_index < 2; type_index++) for (unsigned htc = 0; htc < 2; htc++) {
        u8 type = type_index ? ASSOC_RSP : ASSOC_REQ;
        size_t full = build(frame, type, htc, rich, rich_len);
        size_t minimum = MAC_HDR_LEN + (htc ? HT_CTRL_HDR_LEN : 0) + (type_index ? 6 : 4);
        for (size_t length = 0; length < minimum; length++) {
            u8 *short_frame = malloc(length ? length : 1); assert(short_frame);
            memcpy(short_frame, frame, length);
            assert(wland_get_assoc_ies_from_frame(&interface, short_frame, length, type) == -EMSGSIZE);
            assert(!allocations && !calls && !depth && !stations()); free(short_frame);
        }
        for (size_t length = minimum; length < full; length++) {
            /* IE boundaries can be valid prefixes; non-boundaries must fail. */
            if (length == minimum || length == minimum + 5 || length == minimum + 11) continue;
            u8 *short_frame = malloc(length); assert(short_frame); memcpy(short_frame, frame, length);
            assert(wland_get_assoc_ies_from_frame(&interface, short_frame, length, type) == -EMSGSIZE);
            assert(!allocations && !calls && !depth && !stations()); free(short_frame);
        }
        assert(!wland_get_assoc_ies_from_frame(&interface, frame, full, type));
        assert(!depth);
        u8 *previous = type_index ? vif.conn_info.resp_ie : first()->assoc_req_ie;
        assert(!memcmp(previous, rich, rich_len));
        if (!type_index) {
            assert(first()->wmm_enable && first()->n_enable && !first()->connect && !first()->aid);
            for (unsigned i = 0; i < 8; i++) assert(first()->tid_jiffies[i] == jiffies && !first()->tid_num[i]);
        }
        /* Corrupt updates must preserve the existing IE pointer and bytes. */
        calls = 0;
        assert(wland_get_assoc_ies_from_frame(&interface, frame, full - 1, type) == -EMSGSIZE);
        assert((type_index ? vif.conn_info.resp_ie : first()->assoc_req_ie) == previous);
        assert(!memcmp(previous, rich, rich_len) && !calls && !depth);
        calls = 0; fail_call = 1;
        assert(wland_get_assoc_ies_from_frame(&interface, frame, full, type) == -ENOMEM);
        assert((type_index ? vif.conn_info.resp_ie : first()->assoc_req_ie) == previous && !depth);
        fail_call = 0;
        const u8 replacement[] = {0, 1, 'x'};
        full = build(frame, type, htc, replacement, sizeof(replacement));
        assert(!wland_get_assoc_ies_from_frame(&interface, frame, full, type));
        assert(!memcmp(type_index ? vif.conn_info.resp_ie : first()->assoc_req_ie, replacement, sizeof(replacement)));
        if (!type_index) assert(!first()->wmm_enable && !first()->n_enable && stations() == 1);
        full = build(frame, type, htc, NULL, 0);
        assert(!wland_get_assoc_ies_from_frame(&interface, frame, full, type));
        if (type_index) assert(!vif.conn_info.resp_ie && !vif.conn_info.resp_ie_len && !allocations);
        else assert(!first()->assoc_req_ie && !first()->assoc_req_ie_len && !first()->wmm_enable && !first()->n_enable && allocations == 1);
        reset();
    }
    for (unsigned failure = 1; failure <= 2; failure++) {
        size_t full = build(frame, ASSOC_REQ, false, rich, rich_len);
        fail_call = failure;
        assert(wland_get_assoc_ies_from_frame(&interface, frame, full, ASSOC_REQ) == -ENOMEM);
        assert(!allocations && !stations() && !depth); reset();
    }
    size_t full = build(frame, ASSOC_REQ, false, rich, rich_len);
    assert(wland_get_assoc_ies_from_frame(NULL, frame, full, ASSOC_REQ) == -EINVAL);
    struct wland_if missing_vif = {NULL};
    assert(wland_get_assoc_ies_from_frame(&missing_vif, frame, full, ASSOC_REQ) == -EINVAL);
    assert(wland_get_assoc_ies_from_frame(&interface, NULL, full, ASSOC_REQ) == -EINVAL);
    assert(wland_get_assoc_ies_from_frame(&interface, frame, full, ASSOC_RSP) == -EPROTO);
    frame[0] = 0x20;
    assert(wland_get_assoc_ies_from_frame(&interface, frame, full, 0x20) == -EOPNOTSUPP);
    for (unsigned mode = 0; mode < 5; mode++) {
        full = build(frame, ASSOC_REQ, false, rich, rich_len);
        if (mode == 0) frame[0] |= 1;
        if (mode == 1) frame[1] |= 1;
        if (mode == 2) frame[1] |= 2;
        if (mode == 3) { frame[28] = WLAN_EID_SSID; frame[29] = 33; }
        if (mode == 4) frame[40] = 25; /* HT IE length */
        assert(wland_get_assoc_ies_from_frame(&interface, frame, full, ASSOC_REQ) == -EPROTO);
        assert(!allocations && !stations() && !calls && !depth);
    }
    puts("RDA_ASSOC_FRAMES_PASS: actual bounded STA/AP frames, HT headers, IE validation and transactional allocation ownership");
}
'''
code = code.replace("/* CONSTANTS */", constants).replace("/* STRUCTURES */", structures)
code = code.replace("/* TLV HELPERS */", tlv_helpers).replace("/* ACTUAL OPERATION */", operation)
with tempfile.TemporaryDirectory(prefix="rda-assoc-") as directory:
    temp = Path(directory)
    (temp / "assoc.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-pointer-sign",
                    str(temp / "assoc.c"), "-o", str(temp / "assoc")], check=True)
    subprocess.run([str(temp / "assoc")], check=True, timeout=10)
