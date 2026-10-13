# Native OpenWrt Ethernet physical RAM experiment

Later source correction and fresh offline TX ownership/retry checks are
recorded in the [TX report](femac-xmit-20261013.md), including physical corrected
router-image traffic with zero additional error/drop/FIFO counts. This physical
report retains the original native-net image's measured counters.

Date: 2026-10-13. The existing CA fastboot loaded the separate native `net`
image by YMODEM. Device CRC32 matched before `bootm`. This boot and all test
files used RAM; no flash, persistent boot or security-state writes occurred.

## Image and startup

| Item | Observed result |
|---|---|
| uImage bytes | 4689784 |
| uImage SHA-256 | `b2182d940f546032686077278baab6114ddaf6b17a43e39f728afc8bc29e23ee` |
| Device/host image CRC32 | `24b5431a`, matched |
| Kernel release | `6.12.112` |
| Native source revision | `58efa9917d4cc53fceed173529a286187649e827` |
| Native target / board compatible | `hi3798mv100/net` / `tianyi,ty1208z-ca-openwrt-net` |
| PHY | FESTAv220, ID `0x20669823`, address 1 |
| Link | 100 Mbps, full duplex |
| DHCP | `10.0.0.104/24`, gateway `10.0.0.1`; netifd DHCP up |
| Gateway check | 4/4 replies, no loss |
| RAM-file time64 | Timestamp `2208988800`; `sizeof(time_t)=8` |

OpenWrt overrides the requested kernel local-version suffix. The generated
UTS header and physical `uname -r` both report `6.12.112`. The UART collector
now checks this actual release together with the pinned rootfs revision,
native target and exact board compatible before sending an experiment.
Foreign/missing identity cases fail before any experiment script. The built
image checker independently verifies the generated UTS header.

The corrected collector passed its five PTY test methods, including both
native profiles and wrong source/board cases. Repository lint, the diagnostic
build, generic ARM/QEMU time64 and guarded RAM/YMODEM/TFTP regressions passed;
the actual existing native Ethernet image passed its built checker unchanged.
These software checks are distinct from physical observations.

## TCP and independent clock checks

Both ends ran iperf3 3.20. The host executable was built from the pinned,
SHA-verified source; executable SHA-256:
`5fe9745d600b3bded598d738c7cd5391ee8e97222e392d08c5f2844299e7da10`.
The host path includes WLAN and WSL NAT. It does not measure the board's
maximum throughput or routing/Passwall performance.

| Test | Completed receiver bytes | Host reported seconds | Board reported seconds |
|---|---:|---:|---:|
| Host to board, first | 620101632 | 60.011671 | 55.896205 |
| Board to host, first | 652083200 | 60.000524 | 55.697750 |
| Host to board, sampled repeat | 649723904 | 60.001085 | 55.595408 |
| Board to host, sampled repeat | 651558912 | 60.001161 | 55.529891 |

The approximately 7–8% disagreement required independent measurement rather
than changing the board timer frequency. Windows monotonic timestamps bracketed
UART `/proc/uptime` samples, with `hi3798mv100` confirmed as the clocksource.
Over 30 seconds idle, board/Windows elapsed ratio was approximately 0.99996.
During reverse traffic it was 0.999976 over 60.3114 Windows seconds; during
forward traffic it was 1.000002 over 60.3299 Windows seconds. Maximum UART
sample round trips were below 28 ms; uptime has 10-ms output resolution.

A separate timestamped WSL process progressed 25.0037 monotonic seconds while
Windows progressed 23.1907 seconds: WSL/Windows ratio 1.078179. This independently
identifies host WSL clock drift consistent with the TCP duration discrepancy.
No host/board wall time, timer frequency or NTP configuration was changed.
The board's repeat receiver and sender statistics are approximately 93.49 and
93.98 Mbps respectively; host-reported rates use the drifting WSL clock.
Those figures still include this particular WLAN/NAT path and in-flight TCP
accounting; they are not a board benchmark.

RX errors/drops and TX errors remained zero. The first reverse run increased
TX dropped/FIFO counts by 65479; the sampled reverse repeat increased both by
64644. Forward runs did not increase them. Inspection of the actual compiled
FEMAC source confirms both full-queue branches increment these counters
before returning `NETDEV_TX_BUSY`, retaining the skb for stack retry. Therefore
these counters do not establish an equal number of discarded packets, and
must not be reported as a clean zero-drop result. The sampled reverse sender
reported 14 retransmits; the first reverse sender reported 16. Correct busy
accounting and hardware revalidation remain a separate follow-up.

## Local evidence and limits

Raw serial streams, transmit journals and full TCP JSON stay in ignored local
`evidence/`. The published observations omit MAC addresses and personal paths.

| Evidence | SHA-256 |
|---|---|
| Initial network report raw stream | `cb32934c6ad0e2fc6da088a279b243dbfb0c21d8473a82a6f3ec90110c280c58` |
| First forward collector raw stream | `7e3be96ad1bef533bf9ba6a97d61251b9439b4aae901af97d4304cd84e81f898` |
| First reverse collector raw stream | `43601049d7f966a5ec7f9475ac0a3e76d9dbae209c9c46efaff7a52ce07e9c49` |

The cable experiment observed carrier down then up and corresponding driver
link messages, separated by approximately 7.28 board seconds. After reconnect,
netifd DHCP was up at the same address and another four gateway pings passed
with no loss. Its raw stream is retained locally with SHA-256
`8d8fc6a511117b10ff7843c1d02f4fae8a5f425de9070ae6a161c2ffed39bce4`.

Complete PHY cold-start support,
router/LuCI/Passwall acceptance, USB/Wi-Fi, storage and SMP are not established
by this `net` image. It has no SSH or LuCI service. Kernel support for timestamps
beyond 2038 does not establish whole-system Y2038 acceptance.
