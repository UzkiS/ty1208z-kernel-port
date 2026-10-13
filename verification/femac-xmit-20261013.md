# FEMAC transmit backpressure accounting, 2026-10-13

The physically observed native Ethernet image increased `tx_dropped` and
`tx_fifo_errors` whenever either transmit queue was full. Both branches return
`NETDEV_TX_BUSY` without consuming the skb: the stack retains it for retry.
Those counters therefore represented backpressure attempts as packet loss;
the earlier traffic result remains as measured in the
[physical Ethernet report](openwrt-ethernet-board-20261013.md).

The checked FEMAC generator now removes only those two counter pairs. The
stop-queue, variant-specific credit interrupt and BUSY return remain intact.
DMA mapping failure still frees the skb, increases `tx_dropped` once and
returns `NETDEV_TX_OK`. The repeated replacement anchor must occur exactly
twice in the SHA-256-verified Linux 6.12.112 archive; the generated board patch
is committed with the generator.

## Actual-function regression

`tools/test_femac_xmit.py` extracts the complete, unchanged
`hisi_femac_net_xmit()` and IRQ-enable helper from the actual patched Linux
tree. Register constants also come from that source. ASan/UBSan runs both
`mv100_inherited` modes, all 64 ring-head positions, four packet lengths and
empty/partially occupied/full queues. The seams model MMIO, DMA and stack
ownership, rather than replacing the function being tested.

Across 13,312 TX calls, the regression checks:

- 7,680 BUSY returns preserve the skb and payload, all ring entries, DMA state,
  FIFO count, success/drop/FIFO statistics and BQL; only queue stop and the
  correct IRQ-enable operation are permitted.
- 4,096 successful sends, including retries of the same BUSY skb after modeled
  credit/reclamation recovery, map/enqueue exactly once, wrap the head correctly,
  retain other descriptors and update MMIO address/length, bytes/packets and BQL.
- 1,536 DMA failures free exactly once and count one real drop, without queue,
  descriptor, success-statistic or BQL changes.

The old actual native-router source fails the first unchanged-statistics
assertion. The regenerated shared source and freshly rebuilt native-router
source pass both TX and existing RX/NAPI/ISR/monitor regressions. Their full
source identities are:

| Source | SHA-256 |
|---|---|
| Old native FEMAC | `202e8de9bebb10588c89c75b34a5f7ad79a2fc9db67f9ec5ce0efafe7363ada1` |
| Corrected native FEMAC | `241e02357337d81575a09d2abac0da85732f250fe6dab2b324155c997bfc588f` |

The actual native source is also byte-equal to the generator applied to the
verified original archive. The existing datapath runner invokes TX regression,
so standalone Ethernet, native Ethernet and integrated router build entries
execute it. Native/application CI path filters include the generator and TX
tests.

## Build and RAM candidate

Local `make lint`, `make build`, `make test`, `make ethernet-net` and a clean
native-router kernel rebuild completed. Router QEMU passes both 512-MiB and
240-MiB usable budgets, including Xray before NTP, NTP/time64, DNS/TLS,
authenticated UI, SOCKS and netifd/fw4 TCP/UDP TPROXY. All six packaged files,
actual console hashes, source-fixture hashes and required console markers
were independently verified. The RAM planner accepts bounded placement and
external initrd structure for these exact bytes:

| Payload | Bytes | SHA-256 | Whole-file CRC32 |
|---|---:|---|---|
| uImage | 3436544 | `84a4abd0ce8877bed213f97475adf23cab5f6a7cf9e03c57ecff71b3ee44d18f` | `5d9e16b0` |
| External initrd | 21045256 | `abaf0f42801d72ee350eaed080c4bd017f2616f87e6616230fbf4fd169b2452f` | `79944e6b` |

Raw zImage SHA-256:
`329b834337b842113001984da7d13b16f601aed49694da89e5bdc79aeeeafab2`.
The external initrd remains at `0x04000000`; measured loader/header addresses
and the low-16-MiB decompression bound are unchanged. This candidate includes
the previously validated Xray fix and router DHCP peer-DNS default.

| Usable MiB | Actual console bytes | SHA-256 |
|---:|---:|---|
| 512 | 126611 | `37efdb000fa9b22e73269380a7874aee161d97d378c2fede4be3a80cb12c7601` |
| 240 | 126669 | `17ebb9d76d53c395dc5472f6deeb35916ef0948c7392a787e1111927a41e5be7` |

Physical acceptance of this new TX image, zero-drop traffic, external Ethernet
forwarding/performance and fresh CI for the TX change remain pending. QEMU
and ownership seams cannot establish MAC/PHY/DMA behavior on the board. The
currently running physical router image has not acquired this kernel fix.
No flashing, persistent boot change or future physical wall-clock change was
performed.
