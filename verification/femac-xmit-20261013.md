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

## Physical corrected-image acceptance

The exact kernel/initrd above now run on the physical TY1208Z. A fresh stopped
CA-loader inspection, both immutable TFTP receipts, loader sizes and device
CRCs passed. Temporary loader networking was restored before boot. The
Linux/native identity, FESTAv220 ID `0x20669823` at address 1 and 100-Mbps
full-duplex link were verified. The delivered peer-DNS default acquired the
gateway DNS automatically; the installed NTP service set the current 2026
date without a manual date command. The latest user RAM configuration and
credentials were restored with all 15 selected file hashes verified.

Both physical TCP directions completed using the installed iperf3 3.20 and
the source-verified host executable. The host path includes WLAN and WSL NAT.
The earlier [independent clock check](openwrt-ethernet-board-20261013.md)
established WSL clock drift; board seconds below come from its actual endpoint.

| Direction | Actual receiver bytes | Board iperf seconds | Windows-sampled board/host elapsed ratio | TX drop / FIFO delta |
|---|---:|---:|---:|---|
| Host to board | 643956736 | 55.156649 | 1.000033 | 0 / 0 |
| Board to host | 644481024 | 55.056604 | 0.999673 | 0 / 0 |

RX errors/drops/FIFO/frame and TX errors/carrier also had zero increments in
both runs. The initial cumulative `tx_dropped` was 3 and remained 3; its cause
has not been established. This is zero additional drop accounting during the
measured traffic, not a zero lifetime drop claim. The real DMA-failure path
still counts drops. TCP sender retransmits were 102 forward and 13 reverse;
the WLAN/NAT endpoint test does not locate their cause.

Every timestamped sample and both endpoint JSON files were saved and
independently compared with the summary and counter deltas. SSH round trips
reached 5.04 seconds during forward load and 0.434 seconds during reverse
load, so individual midpoint samples are not precise clock calibration. The
overall elapsed observations are consistent with the earlier UART result.
The initial harness mistakenly required receive bytes from the reverse
server, which is the sender. It cleaned its temporary rule on failure; the
corrected direction-aware harness then completed both directions and cleanup.

Configuration hashes remained unchanged, the source/port-limited temporary
input rule was removed, gateway ping passed 4/4 and the RAM-file time64 probe
passed. The installed Passwall HTTPS/SOCKS/forwarding/TCP/UDP TPROXY namespace
fixture also passed again on this exact kernel, with independent configuration,
namespace and counter-table cleanup checks. See the
[updated board report](openwrt-router-board-20261013.md).

| Local evidence | SHA-256 |
|---|---|
| Corrected TFTP/boot stream | `b891e380672c86a24a981b008e3a790b0be7e2fcfff16fb9c1e37033b6e7bde6` |
| Cold-default DNS/NTP observation | `594cf3b148d9acbd991dd0a1ecab026d371ba5817d1b2d5e234a46a46e2081dc` |
| Full traffic summary and samples | `13b488494ab5c96ca1c517d923b58036392c3892cc479d2d026b6b25a467b13c` |
| Post-traffic gateway/time64/config checks | `bb84d581af87f4bc937c98d8934291d00dbe256984dbbdd61c69a604350e8410` |

External Ethernet forwarding/performance remains pending. These are physical
TCP endpoint and local veth application tests, not a routing benchmark. No
flashing, persistent boot change or future physical wall-clock change was
performed.

## Fresh remote TX regression

Diagnostic CI [38354999973](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38354999973)
completed successfully on `b9b1fe351c804eb9105e8041451e20cdeebba2fb`.
All 11 downloaded profile manifests and their 109 files were independently
checked against actual bytes/SHA-256. Ten uImages passed header/payload CRC,
load/entry and exact zImage-plus-DTB checks. The downloaded Wi-Fi patches
matched this exact Git revision; its eight actual sanitizer markers passed.

The actual Ethernet log contains `ETHERNET_PROBE_GUARDS_PASS`,
`ETHERNET_NET_HELPERS_PASS`, `FEMAC_DATAPATH_PASS` and `FEMAC_XMIT_PASS`;
SHA-256 `d8a28b72eb4c0d47673df25af837d3c003d94b9b8569394fedc2d3a0dc4ef57a`.
This is fresh standalone diagnostic/Ethernet software acceptance, separate
from the physical native-router image above. Native/application CI for this
revision remains queued and does not inherit this run's result.
