#!/usr/bin/env python3
"""Run the actual patched RX/TX/NAPI/ISR functions with FIFO and skb seams."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from test_femac_xmit import run as run_xmit

ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
typedef uintptr_t dma_addr_t;
typedef int irqreturn_t;
#define __iomem
#define BIT(x) (1U << (x))
#define IRQ_NONE 0
#define IRQ_HANDLED 1
#define unlikely(x) (x)
#define likely(x) (x)
#define ETH_HLEN 14
#define ETH_FCS_LEN 4
#define MAX_FRAME_SIZE 1600
#define DMA_FROM_DEVICE 1
#define GLB_IRQ_RAW 0x38
#define GLB_IRQ_STAT 0x30
#define GLB_IRQ_ENA 0x34
#define IQFRM_DES 0x354
#define RX_FRAME_LEN_MASK 0xfff
#define IRQ_INT_RX_RDY BIT(0)
#define IRQ_INT_TX_PER_PACKET BIT(1)
#define IRQ_INT_TX_FIFO_EMPTY BIT(6)
#define DEF_INT_MASK (BIT(7) | BIT(1) | BIT(6))
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
#define from_timer(var, timer, member) container_of(timer, struct hisi_femac_priv, member)
#define READ_ONCE(value) (value)
#define msecs_to_jiffies(value) (value)
#define netdev_err(...) ((void)0)
struct sk_buff { u32 len; int protocol; unsigned char data[MAX_FRAME_SIZE]; };
struct napi_struct { int unused; };
struct timer_list { int unused; };
struct hisi_femac_queue {
    struct sk_buff *skb[128]; dma_addr_t dma_phys[128];
    u32 num, head, tail;
};
struct net_device {
    struct { u32 rx_packets, rx_bytes, rx_errors, rx_length_errors; } stats;
    void *priv;
    bool running;
};
struct hisi_femac_priv {
    void *glb_base, *port_base, *dev;
    struct net_device *ndev;
    struct hisi_femac_queue rxq;
    struct napi_struct napi;
    u32 irq_mask;
    bool mv100_inherited;
    struct timer_list tx_monitor;
    u32 tx_fifo_used_cnt;
};
static u32 global[128], port[256];
static u32 frame_lengths[128], frame_index, frame_count, raw_reads;
static u32 stale_tx, unmaps, frees, put_count, delivered, refills, reclaimed, scheduled, completed;
static unsigned char *allocation;
static bool inject_rx_on_read;
static unsigned long jiffies = 100;
static unsigned int timer_rearmed;
static void *netdev_priv(struct net_device *dev) { return dev->priv; }
static u32 readl(void *address)
{
    if (address == &global[GLB_IRQ_RAW / 4]) {
        /* A sticky/level TX-ready bit must not make NAPI loop without RX. */
        assert(++raw_reads < 100);
        if (inject_rx_on_read && raw_reads == 2) {
            inject_rx_on_read = false;
            frame_count = 1;
        }
        return (frame_index < frame_count ? IRQ_INT_RX_RDY : 0) | stale_tx;
    }
    if (address == &global[GLB_IRQ_STAT / 4])
        return readl(&global[GLB_IRQ_RAW / 4]) & global[GLB_IRQ_ENA / 4];
    if (address == &port[IQFRM_DES / 4]) {
        assert(frame_index < frame_count);
        return frame_lengths[frame_index];
    }
    return *(u32 *)address;
}
static void writel(u32 value, void *address)
{
    if (address == &global[GLB_IRQ_RAW / 4]) {
        if (value & IRQ_INT_RX_RDY) {
            assert(frame_index < frame_count);
            frame_index++; /* Actual RX acknowledgment pops the descriptor. */
        }
        return; /* Level TX-ready remains asserted until hardware credits change. */
    }
    *(u32 *)address = value;
}
static void hisi_femac_irq_enable(struct hisi_femac_priv *priv, int mask)
{ (void)priv; global[GLB_IRQ_ENA / 4] |= mask; }
static void hisi_femac_irq_disable(struct hisi_femac_priv *priv, int mask)
{ (void)priv; global[GLB_IRQ_ENA / 4] &= ~mask; }
static void dma_unmap_single(void *dev, dma_addr_t addr, u32 length, int direction)
{ (void)dev; (void)addr; assert(length == 1600 && direction == 1); unmaps++; }
static void dev_kfree_skb_any(struct sk_buff *skb)
{ assert(skb); frees++; }
static void skb_put(struct sk_buff *skb, u32 length)
{
    /* An oversized put reproduces real skb-tail corruption under ASan. */
    memset(skb->data + skb->len, 0x5a, length);
    skb->len += length; put_count++;
}
static int eth_type_trans(struct sk_buff *skb, struct net_device *dev)
{ (void)dev; assert(skb->len >= ETH_HLEN); return 0x800; }
static void napi_gro_receive(struct napi_struct *napi, struct sk_buff *skb)
{ (void)napi; assert(skb->len <= MAX_FRAME_SIZE); delivered++; }
static void hisi_femac_rx_refill(struct hisi_femac_priv *priv)
{ (void)priv; refills++; }
static void hisi_femac_xmit_reclaim(struct net_device *dev)
{ (void)dev; reclaimed++; }
static void napi_complete_done(struct napi_struct *napi, int work)
{ (void)napi; assert(work >= 0); completed++; }
static void napi_schedule(struct napi_struct *napi)
{ (void)napi; scheduled++; }
static bool netif_running(struct net_device *dev) { return dev->running; }
static void mod_timer(struct timer_list *timer, unsigned long expires)
{ (void)timer; assert(expires == jiffies + 20); timer_rearmed++; }
/* The production receive helper is pulled in after definitions needed by it. */
static bool hi3798mv100_femac_valid_length(u32 frame);
"""

MAIN = r"""
static struct net_device ndev;
static struct hisi_femac_priv priv;
static void initialize(void)
{
    memset(&ndev, 0, sizeof(ndev)); memset(&priv, 0, sizeof(priv));
    memset(global, 0, sizeof(global)); memset(port, 0, sizeof(port));
    frame_index = frame_count = raw_reads = stale_tx = 0;
    unmaps = frees = put_count = delivered = refills = reclaimed = scheduled = completed = 0;
    inject_rx_on_read = false;
    timer_rearmed = 0;
    priv.ndev = &ndev; ndev.priv = &priv;
    priv.glb_base = global; priv.port_base = port;
    priv.mv100_inherited = true;
    priv.irq_mask = IRQ_INT_RX_RDY | IRQ_INT_TX_FIFO_EMPTY;
    priv.rxq.num = 128;
}
static struct sk_buff *buffer(void)
{
    struct sk_buff *skb = calloc(1, sizeof(*skb)); assert(skb);
    allocation = (void *)skb; return skb;
}
int main(void)
{
    /* Execute the actual RX function for every masked descriptor length. */
    for (u32 len = 0; len <= 4095; len++) {
        initialize(); frame_count = 1; frame_lengths[0] = len;
        priv.rxq.skb[0] = buffer();
        assert(hisi_femac_rx(&ndev, 1) == 1);
        assert(frame_index == 1 && priv.rxq.tail == 1 && unmaps == 1);
        bool valid = len >= ETH_HLEN + ETH_FCS_LEN && len <= MAX_FRAME_SIZE;
        assert(put_count == valid && delivered == valid && frees == !valid);
        assert(ndev.stats.rx_packets == valid && ndev.stats.rx_errors == !valid);
        assert(ndev.stats.rx_bytes == (valid ? len - ETH_FCS_LEN : 0));
        free(allocation);
    }
    /* Sticky TX-only status cannot consume unbounded polls. */
    initialize(); stale_tx = IRQ_INT_TX_FIFO_EMPTY;
    assert(hisi_femac_poll(&priv.napi, 16) == 0);
    assert(raw_reads <= 3 && reclaimed == 1 && completed == 1);
    assert(global[GLB_IRQ_ENA / 4] == IRQ_INT_RX_RDY);
    /* NAPI zero budget is TX-only and must neither pop RX nor complete NAPI. */
    initialize(); frame_count = 1; frame_lengths[0] = 64;
    assert(hisi_femac_poll(&priv.napi, 0) == 0);
    assert(frame_index == 0 && refills == 0 && completed == 0 && reclaimed == 1);
    /* ISR acknowledges TX, preserving the pending RX descriptor for NAPI. */
    initialize(); frame_count = 1; frame_lengths[0] = 64;
    global[GLB_IRQ_ENA / 4] = priv.irq_mask;
    assert(hisi_femac_interrupt(0, &ndev) == IRQ_HANDLED);
    assert(scheduled == 1 && frame_index == 0 && global[GLB_IRQ_ENA / 4] == 0);
    /* The interrupt belongs to another shared-IRQ device when ours is masked. */
    initialize(); stale_tx = IRQ_INT_TX_FIFO_EMPTY;
    assert(hisi_femac_interrupt(0, &ndev) == IRQ_NONE && scheduled == 0);
    /* RX arriving as poll inspects pending flags must still be consumed. */
    initialize(); frame_lengths[0] = 64;
    priv.rxq.skb[0] = buffer(); inject_rx_on_read = true;
    assert(hisi_femac_poll(&priv.napi, 16) == 1);
    assert(delivered == 1 && frame_index == 1 && completed == 1);
    free(allocation);
    /* Budget exhaustion keeps NAPI active; later packets aren't acknowledged. */
    initialize(); frame_count = 2; frame_lengths[0] = frame_lengths[1] = 64;
    priv.rxq.skb[0] = buffer();
    assert(hisi_femac_poll(&priv.napi, 1) == 1);
    assert(frame_index == 1 && completed == 0 && global[GLB_IRQ_ENA / 4] == 0);
    free(allocation);
    /* TX buffers are periodically reclaimed without depending on incoming RX. */
    initialize(); priv.tx_fifo_used_cnt = 1;
    hisi_femac_mv100_tx_monitor(&priv.tx_monitor);
    assert(scheduled == 0 && timer_rearmed == 0);
    ndev.running = true; priv.tx_fifo_used_cnt = 0;
    hisi_femac_mv100_tx_monitor(&priv.tx_monitor);
    assert(scheduled == 0 && timer_rearmed == 1);
    priv.tx_fifo_used_cnt = 1;
    hisi_femac_mv100_tx_monitor(&priv.tx_monitor);
    assert(scheduled == 1 && timer_rearmed == 2);
    puts("FEMAC_DATAPATH_PASS: actual RX lengths, RX-preserving ISR, TX-level bound, budgets");
    return 0;
}
"""


def extract(source, begin, end):
    start = source.index(begin)
    return source[start:source.index(end, start)]


def run(linux):
    source = (linux / "drivers/net/ethernet/hisilicon/hisi_femac.c").read_text()
    helper = (ROOT / "overlay/drivers/net/ethernet/hisilicon/hi3798mv100-femac.h").read_text()
    receive = extract(source, "static int hisi_femac_rx(", "static int hisi_femac_poll(")
    poll = extract(source, "static int hisi_femac_poll(", "static irqreturn_t hisi_femac_interrupt(")
    interrupt = extract(source, "static irqreturn_t hisi_femac_interrupt(", "static int hisi_femac_init_queue(")
    length = extract(helper, "static inline bool hi3798mv100_femac_valid_length(", "#endif")
    monitor = extract(source, "static void hisi_femac_mv100_tx_monitor(", "static int hisi_femac_net_open(")
    with tempfile.TemporaryDirectory(prefix="femac-datapath-") as directory:
        build = Path(directory)
        cfile = build / "test.c"
        # Keep real source unchanged. Inline helper spelling matches its header.
        prelude = PRELUDE.replace("static bool hi3798mv100_femac_valid_length",
                                  "static inline bool hi3798mv100_femac_valid_length")
        cfile.write_text(prelude + length + receive + poll + interrupt + monitor + MAIN)
        binary = build / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", "-Wno-sign-compare",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(cfile), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True, timeout=10)
    run_xmit(linux)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux", type=Path, required=True)
    args = parser.parse_args()
    run(args.linux)
