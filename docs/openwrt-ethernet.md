# Independent native Ethernet RAM experiment

`make openwrt-net TASKBASE=<native-build-base>` builds a separate OpenWrt
Ethernet image after the fixed native compiler/musl installation is complete.
`make openwrt-net-config` resolves and checks the configuration only.
Sources live in `<native-build-base>/ethernet`; the plain RAM target and
application-validation tree keep their own output directories.

The `net` subtarget inherits the measured single-core UART/timer/low-256-MiB
memory description and the separate diagnostic Ethernet DTS. Its root
compatible is `tianyi,ty1208z-ca-openwrt-net`. The native OpenWrt build fixes
the actual UTS release to `6.12.112` despite the requested local-version
configuration. Both the built-header checker and UART collector require that
actual release; the collector also checks the pinned rootfs revision, native
target and board-compatible identity. Clock, PHY and MAC guards recognize this
profile while retaining exact measured resources, inherited-state controls,
32-bit DMA, dedicated FESTAv220 identity and no-reset behavior. The original
diagnostic profile cannot borrow the native profile's identity.

The build references the authoritative board patch; it does not duplicate
drivers or import standalone kernel modules. The compiler/musl reuse helper
belongs to the native source layer. No Passwall or other application feed is
required: only the complete pinned iperf3 recipe is copied from a SHA-256
verified packages archive, preserving its license and upstream source hash.

netifd configures loopback and one DHCP client on `eth0`. The experiment has
no DHCP server, firewall4, SSH daemon, Wi-Fi or persistent storage support.
The image includes iperf3, ethtool and actual ARM BusyBox ping/HTTP/netcat/hash
tools. Servers are started only for explicit bounded test operations.

The build checks resolved OpenWrt selection, manifest identities, actual
kernel configuration and compiled DT, uImage structure/CRC, appended DTB,
decompression footprint and actual installed rootfs tools/configuration.
It extracts the actual patched Ethernet datapath functions for ASan/UBSan
regression. QEMU runs native procd/ubus/UCI/logging and core time64 at 2040,
plus an iperf3 loopback exchange; no guest NIC is attached and QEMU does not
validate the MV100 MAC/PHY/DMA.

Canonical boot inputs are exported to `artifacts/openwrt-net1`. The common
RAM planner independently enforces low-16-MiB decompression, low-256-MiB RAM,
measured CA loader commands/addresses, the exact native Ethernet profile
and disabled storage/USB/modules/SMP. No installation recipe is defined.

After a separately planned RAM boot, use:

```text
python tools/openwrt_ethernet_board_cli.py --port COM9
python tools/openwrt_ethernet_board_cli.py --port COM9 --iperf-start
python tools/openwrt_ethernet_board_cli.py --port COM9 --iperf-collect
```

The CLI refuses bootloader/Hinas/foreign-rootfs identities, records raw RX,
TX journal and metadata, and requires standalone completion markers. The
iperf server binds the lease address, accepts one test and has a 60-second
idle timeout. Reports stay local until anonymized. Build acceptance does
not establish physical OpenWrt networking or router/Passwall throughput;
those require their own evidence.

The separate native `net` image has now passed physical RAM startup, DHCP,
bidirectional TCP and cable down/up recovery; see the [board report](../verification/openwrt-ethernet-board-20261013.md).
That report also distinguishes measured host WSL clock drift and the driver's
busy-queue counter semantics from hardware drops and router performance.
The two BUSY branches now preserve drop/FIFO statistics, with actual-function
ownership/retry/DMA regression and rebuilt Ethernet/router acceptance recorded
in the [TX report](../verification/femac-xmit-20261013.md). The corrected
kernel's physical traffic result remains pending.
