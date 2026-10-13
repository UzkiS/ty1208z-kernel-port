#!/usr/bin/env python3
"""Execute the actual FEMAC TX function with DMA, skb and MMIO ownership seams."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

PRELUDE = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
typedef uintptr_t dma_addr_t;
typedef int netdev_tx_t;
#define BIT(x) (1U << (x))
#define CIRC_SPACE(head, tail, size) (((tail) - ((head) + 1)) & ((size) - 1))
#define unlikely(x) (x)
#define NETDEV_TX_OK 0
#define NETDEV_TX_BUSY 0x10
#define DMA_TO_DEVICE 1
#define ETH_FCS_LEN 4
"""

SEAMS = r"""
struct sk_buff { u32 len; unsigned char data[MAX_FRAME_SIZE]; };
struct hisi_femac_queue {
    struct sk_buff **skb;
    dma_addr_t *dma_phys;
    int num;
    unsigned int head, tail;
};
struct tx_stats { uint64_t tx_packets, tx_bytes, tx_dropped, tx_fifo_errors; };
struct net_device { struct tx_stats stats; void *priv; bool stopped; };
struct hisi_femac_priv {
    void *port_base, *glb_base, *dev;
    struct hisi_femac_queue txq;
    bool mv100_inherited;
    u32 tx_fifo_used_cnt;
};
static struct net_device ndev;
static struct hisi_femac_priv priv;
static struct sk_buff occupied[TXQ_NUM], *slots[TXQ_NUM], *active;
static dma_addr_t addresses[TXQ_NUM];
static u32 port[0x400 / 4], global[0x200 / 4];
static u32 maps, map_checks, frees, stops, sent, sent_bytes;
static u32 status_reads, irq_reads, irq_writes, descriptor_writes;
static bool fail_dma;
static const dma_addr_t mapped = 0x12345000;
static void *netdev_priv(struct net_device *dev)
{ assert(dev == &ndev); return dev->priv; }
static u32 readl(void *address)
{
    if (address == &port[ADDRQ_STAT / 4]) status_reads++;
    else { assert(address == &global[GLB_IRQ_ENA / 4]); irq_reads++; }
    return *(u32 *)address;
}
static void writel(u32 value, void *address)
{
    if (address == &global[GLB_IRQ_ENA / 4]) irq_writes++;
    else if (address == &port[EQ_ADDR / 4]) {
        assert(descriptor_writes == 0 && value == mapped);
        descriptor_writes++;
    } else {
        assert(address == &port[EQFRM_LEN / 4]);
        assert(descriptor_writes == 1 && value == active->len + ETH_FCS_LEN);
        descriptor_writes++;
    }
    *(u32 *)address = value;
}
static void netif_stop_queue(struct net_device *dev)
{ assert(dev == &ndev); dev->stopped = true; stops++; }
static dma_addr_t dma_map_single(void *dev, void *data, u32 length, int direction)
{
    assert(dev == &priv && data == active->data && length == active->len);
    assert(direction == DMA_TO_DEVICE && length && length <= MAX_FRAME_SIZE);
    assert(active->data[length - 1] == 0xa5);
    maps++;
    return fail_dma ? ~(dma_addr_t)0 : mapped;
}
static bool dma_mapping_error(void *dev, dma_addr_t address)
{ assert(dev == &priv); map_checks++; return address == ~(dma_addr_t)0; }
static void dev_kfree_skb_any(struct sk_buff *skb)
{ assert(skb == active); frees++; free(skb); }
static void netdev_sent_queue(struct net_device *dev, u32 bytes)
{ assert(dev == &ndev && bytes == active->len); sent++; sent_bytes += bytes; }
"""

MAIN = r"""
struct snapshot {
    struct tx_stats stats;
    struct hisi_femac_priv priv;
    struct sk_buff *slots[TXQ_NUM];
    dma_addr_t addresses[TXQ_NUM];
    u32 port[0x400 / 4], global[0x200 / 4];
    struct sk_buff skb;
};
static struct snapshot before;
static void snapshot(void)
{
    before.stats = ndev.stats; before.priv = priv;
    memcpy(before.slots, slots, sizeof(slots));
    memcpy(before.addresses, addresses, sizeof(addresses));
    memcpy(before.port, port, sizeof(port));
    memcpy(before.global, global, sizeof(global));
    before.skb = *active;
}
static void initialize(bool inherited, u32 head, u32 count, u32 length)
{
    memset(&ndev, 0, sizeof(ndev)); memset(&priv, 0, sizeof(priv));
    memset(slots, 0, sizeof(slots)); memset(addresses, 0, sizeof(addresses));
    memset(port, 0, sizeof(port)); memset(global, 0, sizeof(global));
    maps = map_checks = frees = stops = sent = sent_bytes = 0;
    status_reads = irq_reads = irq_writes = descriptor_writes = 0;
    fail_dma = false;
    ndev.priv = &priv; priv.dev = &priv;
    priv.port_base = port; priv.glb_base = global;
    priv.mv100_inherited = inherited;
    priv.txq.skb = slots; priv.txq.dma_phys = addresses; priv.txq.num = TXQ_NUM;
    priv.txq.head = head; priv.txq.tail = (head + TXQ_NUM - count) % TXQ_NUM;
    priv.tx_fifo_used_cnt = count;
    for (u32 n = 0; n < count; n++) {
        u32 index = (priv.txq.tail + n) % TXQ_NUM;
        slots[index] = &occupied[index]; addresses[index] = 0x20000000 + index * 1600;
    }
    /* Nonzero baselines also detect accidental counter resets. */
    ndev.stats = (struct tx_stats){100, 12000, 7, 3};
    global[GLB_IRQ_ENA / 4] = BIT(0) | BIT(18) | BIT(19);
    port[ADDRQ_STAT / 4] = BIT_TX_READY | BIT(25) | 3;
    port[EQ_ADDR / 4] = 0xdead0000; port[EQFRM_LEN / 4] = 63;
    active = calloc(1, sizeof(*active)); assert(active);
    active->len = length; memset(active->data, 0xa5, sizeof(active->data));
}
static void unchanged_queue(void)
{
    assert(memcmp(&priv, &before.priv, sizeof(priv)) == 0);
    assert(memcmp(slots, before.slots, sizeof(slots)) == 0);
    assert(memcmp(addresses, before.addresses, sizeof(addresses)) == 0);
    assert(memcmp(port, before.port, sizeof(port)) == 0);
}
static void busy(void)
{
    snapshot();
    assert(hisi_femac_net_xmit(active, &ndev) == NETDEV_TX_BUSY);
    /* BUSY leaves ownership entirely with the stack for the same skb retry. */
    assert(memcmp(&ndev.stats, &before.stats, sizeof(ndev.stats)) == 0);
    unchanged_queue();
    assert(memcmp(active, &before.skb, sizeof(*active)) == 0);
    assert(maps == 0 && map_checks == 0 && frees == 0 && sent == 0);
    assert(ndev.stopped && descriptor_writes == 0);
    assert(irq_reads == stops && irq_writes == stops && status_reads == stops);
    u32 mask = priv.mv100_inherited ? IRQ_INT_TX_FIFO_EMPTY : IRQ_INT_TX_PER_PACKET;
    before.global[GLB_IRQ_ENA / 4] |= mask;
    assert(memcmp(global, before.global, sizeof(global)) == 0);
}
static void success(void)
{
    snapshot(); u32 old_head = priv.txq.head;
    u32 old_stops = stops, old_irqs = irq_writes, old_reads = status_reads;
    assert(hisi_femac_net_xmit(active, &ndev) == NETDEV_TX_OK);
    assert(maps == 1 && map_checks == 1 && frees == 0);
    assert(sent == 1 && sent_bytes == active->len && descriptor_writes == 2);
    assert(stops == old_stops && irq_writes == old_irqs && status_reads == old_reads + 1);
    assert(memcmp(active, &before.skb, sizeof(*active)) == 0);
    before.slots[old_head] = active; before.addresses[old_head] = mapped;
    before.priv.txq.head = (old_head + 1) % TXQ_NUM;
    before.priv.tx_fifo_used_cnt++;
    before.port[EQ_ADDR / 4] = mapped;
    before.port[EQFRM_LEN / 4] = active->len + ETH_FCS_LEN;
    unchanged_queue();
    before.stats.tx_packets++; before.stats.tx_bytes += active->len;
    assert(memcmp(&ndev.stats, &before.stats, sizeof(ndev.stats)) == 0);
    assert(memcmp(global, before.global, sizeof(global)) == 0);
    free(active);
}
int main(void)
{
    assert(TXQ_NUM == 64);
    const u32 lengths[] = {14, 60, 1514, MAX_FRAME_SIZE};
    const u32 counts[] = {0, 1, TXQ_NUM - 2, TXQ_NUM - 1};
    for (u32 inherited = 0; inherited < 2; inherited++) {
        for (u32 head = 0; head < TXQ_NUM; head++) {
            for (u32 l = 0; l < sizeof(lengths) / sizeof(lengths[0]); l++) {
                for (u32 c = 0; c < sizeof(counts) / sizeof(counts[0]); c++) {
                    /* Hardware credits exhausted, including simultaneous ring full. */
                    initialize(inherited, head, counts[c], lengths[l]);
                    port[ADDRQ_STAT / 4] &= ~BIT_TX_READY;
                    busy(); busy(); busy();
                    port[ADDRQ_STAT / 4] |= BIT_TX_READY;
                    if (counts[c] == TXQ_NUM - 1) {
                        /* Model one completed descriptor before the stack retries. */
                        u32 tail = priv.txq.tail;
                        slots[tail] = NULL; addresses[tail] = 0;
                        priv.txq.tail = (tail + 1) % TXQ_NUM;
                        priv.tx_fifo_used_cnt--;
                    }
                    ndev.stopped = false; success();
                }
                /* Software ring full despite available hardware credit. */
                initialize(inherited, head, TXQ_NUM - 1, lengths[l]);
                busy(); busy(); busy();
                u32 tail = priv.txq.tail;
                slots[tail] = NULL; addresses[tail] = 0;
                priv.txq.tail = (tail + 1) % TXQ_NUM;
                priv.tx_fifo_used_cnt--;
                ndev.stopped = false; success();
                for (u32 c = 0; c < 3; c++) {
                    /* Real DMA failure consumes/frees the skb and counts one drop. */
                    initialize(inherited, head, counts[c], lengths[l]);
                    fail_dma = true; snapshot();
                    assert(hisi_femac_net_xmit(active, &ndev) == NETDEV_TX_OK);
                    assert(maps == 1 && map_checks == 1 && frees == 1);
                    assert(sent == 0 && sent_bytes == 0 && descriptor_writes == 0);
                    assert(stops == 0 && !ndev.stopped && irq_writes == 0 && status_reads == 1);
                    unchanged_queue();
                    before.stats.tx_dropped++;
                    assert(memcmp(&ndev.stats, &before.stats, sizeof(ndev.stats)) == 0);
                    assert(memcmp(global, before.global, sizeof(global)) == 0);
                    initialize(inherited, head, counts[c], lengths[l]); success();
                }
            }
        }
    }
    puts("FEMAC_XMIT_PASS: actual BUSY ownership/retry, ring wrap, DMA drop, descriptors and BQL");
    return 0;
}
"""


def run(linux):
    source = (linux / "drivers/net/ethernet/hisilicon/hisi_femac.c").read_text()
    constants = []
    for name in ("TXQ_NUM", "MAX_FRAME_SIZE", "EQ_ADDR", "EQFRM_LEN", "ADDRQ_STAT",
                 "BIT_TX_READY", "GLB_IRQ_ENA", "IRQ_INT_TX_PER_PACKET", "IRQ_INT_TX_FIFO_EMPTY"):
        matches = re.findall(rf"^#define\s+{name}\s+[^\n]+$", source, re.MULTILINE)
        assert len(matches) == 1, f"Changed FEMAC constant: {name}"
        constants.append(matches[0] + "\n")
    start = source.index("static netdev_tx_t hisi_femac_net_xmit(")
    xmit = source[start:source.index("static int hisi_femac_set_mac_address(", start)]
    start = source.index("static void hisi_femac_irq_enable(")
    irq = source[start:source.index("static void hisi_femac_irq_disable(", start)]
    with tempfile.TemporaryDirectory(prefix="femac-xmit-") as directory:
        build = Path(directory)
        cfile = build / "test.c"
        cfile.write_text(PRELUDE + "".join(constants) + SEAMS + irq + xmit + MAIN)
        binary = build / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(cfile), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True, timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux", type=Path, required=True)
    args = parser.parse_args()
    run(args.linux)
