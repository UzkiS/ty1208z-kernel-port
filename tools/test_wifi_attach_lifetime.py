#!/usr/bin/env python3
"""Run actual cfg80211 attach/cleanup with allocation failures under sanitizers."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
args = parser.parse_args()
source = (args.source / 'rdawlan/wland_cfg80211.c').read_text()
names = ('wland_init_connect_info', 'wland_deinit_connect_info',
         'wland_free_vif', 'wland_deinit_priv_mem', 'wland_init_priv_mem',
         'wland_cfg80211_attach')
functions = []
for name in names:
    spans = function_spans(source, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    functions.append(source[start:end])
defs = (args.source / 'rdawlan/wland_defs.h').read_text()
usb = defs.split('#ifdef WLAND_USB_SUPPORT\n', 1)[1].split('/* define for use random', 1)[0]
assert '#define WLAND_P2P_SUPPORT' not in usb

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int32_t s32;
#define GFP_KERNEL 0
#define WLAND_EXTRA_BUF_MAX 16
#define WLAND_ERR_MODE 0
#define NL80211_IFTYPE_STATION 2
#define SCAN_VERSION_NUM 1
#define SCAN_STATE_IDLE 0
#define P2PAPI_BSSCFG_PRIMARY 0
#define WLAND_D11N_IOTYPE 0
#define WLAND_DBG(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define PTR_ERR(p) ((intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
struct list_head { struct list_head *next, *prev; };
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define INIT_LIST_HEAD(h) ((h)->next = (h), (h)->prev = (h))
#define list_for_each_entry(p, h, member) \
    for (p = container_of((h)->next, __typeof__(*p), member); \
         &p->member != (h); p = container_of(p->member.next, __typeof__(*p), member))
#define list_for_each_entry_safe(p, t, h, member) \
    for (p = container_of((h)->next, __typeof__(*p), member), \
         t = container_of(p->member.next, __typeof__(*p), member); \
         &p->member != (h); p = t, t = container_of(t->member.next, __typeof__(*t), member))
static void list_add_tail(struct list_head *p, struct list_head *h) {
    p->prev = h->prev; p->next = h; h->prev->next = p; h->prev = p;
}
static void list_del(struct list_head *p) { p->prev->next = p->next; p->next->prev = p->prev; }
struct timer_list { bool initialized, stopped; };
struct work_struct { bool initialized, cancelled; };
struct workqueue_struct { struct wland_cfg80211_connect_info *owner; };
#define timer_setup(t, cb, f) ((t)->initialized = true, (t)->stopped = false)
#define INIT_WORK(w, cb) ((w)->initialized = true, (w)->cancelled = false)
static void timer_shutdown_sync(struct timer_list *t) { assert(t->initialized); t->stopped = true; }
static void cancel_work_sync(struct work_struct *w) { assert(w->initialized); w->cancelled = true; }
static void spin_lock_init(int *p) { *p = 1; }
static void spin_lock_bh(int *p) { assert(*p); }
static void spin_unlock_bh(int *p) { assert(*p); }
static void atomic_set(int *p, int n) { *p = n; }
#define jiffies 123
#define init_waitqueue_head(p) (*(p) = 1)
#define mutex_init(p) (*(p) = 1)
#define init_completion(p) (*(p) = 1)
struct wland_cfg80211_vif;
struct wland_if;
struct wiphy;
struct device { struct device *parent; };
struct wireless_dev { struct net_device *netdev; struct wiphy *wiphy; };
struct net_device { struct device dev; struct wireless_dev *ieee80211_ptr; struct wland_if *private; };
struct wland_if { struct net_device *ndev; struct wland_cfg80211_vif *vif; };
struct wland_private { struct wland_if *iflist[1]; };
struct wland_cfg80211_connect_info {
    bool initialized, timer_on; struct net_device *ndev; void *data;
    struct timer_list timer, connect_restorework_timeout;
    struct work_struct work, connect_restorework_timeout_work;
    struct workqueue_struct *connect_wq;
    int tid_map, tid_jiffies[8], tid_num[8], sta_info_lock;
    struct list_head sta_info_list;
    void *req_ie, *resp_ie; int req_ie_len, resp_ie_len;
};
struct wland_cfg80211_vif {
    struct wland_if *ifp; struct wireless_dev wdev;
    struct { int mode; } profile;
    struct wland_cfg80211_connect_info conn_info;
    struct list_head list;
};
struct wland_sta_info { void *assoc_req_ie; struct list_head list; };
struct wland_cfg80211_conf { int unused; };
struct wland_cfg80211_pmk_list { int unused; };
struct wland_cfg80211_info {
    struct wiphy *wiphy; struct wland_private *pub;
    struct { int vif_wq, vif_event_lock; } vif_event;
    int scanid_wait, usr_sync, scan_result_lock;
    struct list_head vif_list, scan_result_list; int vif_cnt;
    struct { int version, count; } scan_results;
    struct { struct wland_if *ifp; int escan_state; } scan_info;
    struct timer_list scan_timeout; struct work_struct scan_report_work;
    int vif_disabled, disconnecting_wait; bool in_disconnecting, in_waiting;
    void *scan_request; int escan_info;
    bool pwr_save, roam_on, active_scan, dongle_up;
    struct wland_cfg80211_conf *conf; void *extra_buf;
    struct wland_cfg80211_pmk_list *pmk_list;
    struct { struct { struct wland_cfg80211_vif *vif; } bss_idx[1]; } p2p;
    struct { int io_type; } d11inf;
};
struct wiphy { struct wland_cfg80211_info cfg; struct device dev; bool registered; };
static int allocation, fail_at, live, phy_live, callbacks;
static void *kzalloc(size_t n, int flag) {
    (void)flag; if (++allocation == fail_at) return NULL;
    void *p = calloc(1, n); assert(p); live++; return p;
}
static void kfree(void *p) { if (p) { live--; free(p); } }
static void *cfg_to_ndev(struct wland_cfg80211_info *cfg) { return cfg->pub->iflist[0]->ndev; }
static void *netdev_priv(struct net_device *ndev) { return ndev->private; }
#define SET_NETDEV_DEV(n, d) ((n)->dev.parent = (d))
static struct device *wiphy_dev(struct wiphy *phy) { return &phy->dev; }
static void *wiphy_priv(struct wiphy *phy) { return &phy->cfg; }
static struct wiphy *wland_setup_wiphy(struct device *dev) {
    struct wiphy *phy = kzalloc(sizeof(*phy), 0);
    if (!phy) return ERR_PTR(-ENOMEM);
    phy->dev.parent = dev; phy->registered = true; phy_live++; return phy;
}
static void wiphy_unregister(struct wiphy *phy) { assert(phy->registered); phy->registered = false; }
static void wiphy_free(struct wiphy *phy) { assert(!phy->registered); phy_live--; kfree(phy); }
static struct wland_cfg80211_vif *wland_alloc_vif(struct wland_cfg80211_info *cfg, int type, bool block) {
    (void)type; (void)block;
    struct wland_cfg80211_vif *vif = kzalloc(sizeof(*vif), 0);
    if (!vif) return ERR_PTR(-ENOMEM);
    vif->wdev.wiphy = cfg->wiphy; list_add_tail(&vif->list, &cfg->vif_list); cfg->vif_cnt++; return vif;
}
static struct workqueue_struct *create_queue(const char *name, struct wland_cfg80211_connect_info *owner) {
    assert(!strcmp(name, "connect_wq"));
    struct workqueue_struct *queue = kzalloc(sizeof(*queue), 0);
    if (queue) queue->owner = owner;
    return queue;
}
#define create_singlethread_workqueue(name) create_queue(name, conn_info)
static void destroy_workqueue(struct workqueue_struct *queue) {
    struct wland_cfg80211_connect_info *c = queue->owner;
    assert(c->timer.stopped && c->connect_restorework_timeout.stopped);
    assert(c->work.cancelled && c->connect_restorework_timeout_work.cancelled);
    kfree(queue);
}
static void wland_d11_attach(void *p) { (void)p; }
static void wland_register_event_handlers(struct wland_cfg80211_info *cfg) {
    assert(cfg->pub->iflist[0]->vif->conn_info.connect_wq); callbacks++;
}
/* REAL FUNCTIONS */
static void cleanup(struct wland_cfg80211_info *cfg) {
    struct wland_cfg80211_vif *vif, *tmp;
    wland_deinit_connect_info(cfg); wland_deinit_connect_info(cfg);
    wland_deinit_priv_mem(cfg);
    list_for_each_entry_safe(vif, tmp, &cfg->vif_list, list) wland_free_vif(cfg, vif);
    wiphy_unregister(cfg->wiphy); wiphy_free(cfg->wiphy);
}
int main(void) {
    struct device bus = {}, parent = {};
    struct net_device ndev = {};
    struct wland_if ifp = { .ndev = &ndev };
    struct wland_private drvr = { .iflist = { &ifp } };
    ndev.private = &ifp;
    for (int f = 1; f <= 7; f++) {
        allocation = live = phy_live = callbacks = 0; fail_at = f;
        ndev.dev.parent = &parent;
        struct wland_cfg80211_info *cfg = wland_cfg80211_attach(&drvr, &bus);
        if (f <= 6) {
            assert(!cfg && !callbacks && ndev.dev.parent == &parent);
        } else {
            assert(cfg && callbacks == 1 && ifp.vif && ndev.ieee80211_ptr);
            cleanup(cfg);
        }
        assert(!live && !phy_live && !ifp.vif && !ndev.ieee80211_ptr);
    }
    for (int f = 0; f <= 3; f++) {
        struct wland_cfg80211_info cfg = { .pub = &drvr };
        struct wland_cfg80211_vif vifs[3] = {};
        INIT_LIST_HEAD(&cfg.vif_list);
        for (int i = 0; i < 3; i++) list_add_tail(&vifs[i].list, &cfg.vif_list);
        allocation = live = 0; fail_at = f;
        wland_deinit_connect_info(&cfg); /* all three are uninitialized */
        assert(wland_init_connect_info(&cfg) == (f ? -ENOMEM : 0));
        wland_deinit_connect_info(&cfg); wland_deinit_connect_info(&cfg);
        assert(!live);
        for (int i = 0; i < 3; i++) {
            struct wland_cfg80211_connect_info *c = &vifs[i].conn_info;
            assert(!c->initialized && !c->connect_wq);
            if (!f || i < f) {
                assert(c->timer.stopped && c->connect_restorework_timeout.stopped);
                assert(c->work.cancelled && c->connect_restorework_timeout_work.cancelled);
            }
        }
    }
    puts("RDA_ATTACH_LIFETIME_PASS: failed wiphy/vif/private/queue allocations, partial initialization, double cleanup and pointer rollback");
}
'''
code = code.replace('/* REAL FUNCTIONS */', '\n'.join(functions))
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'attach.c').write_text(code)
    subprocess.run(['cc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-Wall', '-Wextra', '-Werror', path / 'attach.c', '-o', path / 'attach'], check=True)
    subprocess.run([path / 'attach'], check=True)
