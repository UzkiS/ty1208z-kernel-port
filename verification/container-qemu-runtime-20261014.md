# Native ARMv7 Docker QEMU runtime — 2026-10-14

Actual native Docker/dockerd 29.6.1, containerd 2.2.5 and runc 1.3.6 pass
container storage, isolation, resource enforcement, DNS, forwarding/NAT,
lifecycle and daemon shutdown in an isolated Cortex-A7 QEMU guest. Tini 0.19.0
is included in the declared package closure; this fixture does not run it as
the container init. This is generic ARMv7 runtime evidence, not physical
Docker, storage, Wi-Fi, final OpenWrt/fw4/Passwall integration or installation.
No board reboot, flash, card-data, persistent boot or security writes occur.

## Reusable entry and actual inputs

`make openwrt-container-qemu TASKBASE=/absolute/linux/build-root` consumes
the separately compiled packages after `make build` and
`make openwrt-container-packages`. It extracts the complete 73-APK dependency
closure from the fixed native source, checking architecture, exact version
constraints and unambiguous providers. The closure includes containerd's
Btrfs dependency; no declared dependency is silently omitted. Native nft
alternatives come from the extracted APK tables, with constrained paths and
payload/collision checks, without executing package service/install scripts
on the host. BusyBox module defaults and depmod use the target root only.

OpenWrt uses official commit `58efa9917d4cc53fceed173529a286187649e827` and
the already pinned official packages feed. This local run reused the cached
native package source and existing application outputs. The dependency
kernel and kmods were actually rebuilt after adding `kmod-nft-nat`; package
staging equality, source/recipe hashes and real ARM version checks passed.
The predecessor package manifest, kernel/config and APK output were archived
before that change. Existing core package binaries were not represented as
newly compiled from a different board patch.

The exact local native board-support patch is `f095834c1b2601b8383556ea1c1d26b406bc36545e6c15fa6237b48bdd9169db`,
as recorded in `native-overlay.json`. It is separate from the current shared
diagnostic/eMMC E848 patch. The current board RAM candidates were not used
or updated for this QEMU run. Fresh CI will build from its checked-out inputs;
the local cached-kernel result is not a clean full-source CI claim.

Actual module/kernel package identity is
`6.12.112~5f994735d907f911b78403d2bcba456b-r1`; generated UTS release is exactly
`6.12.112`. The actual kernel config equals the native package manifest's
exported config byte-for-byte. Module loading succeeds in that kernel.
The runtime manifest records all APK hashes/versions/dependencies, native
compile manifest, native overlay, output files and frozen source hashes.
BusyBox uses the pinned archive/time64 patch and fixed source epoch 1791676800;
the deterministic local Docker archive declares `linux/arm/v7`. No registry
or container-image download is used.

| Output | Bytes | SHA-256 |
|---|---:|---|
| zImage.QEMU-ONLY | 3624128 | `d4454ecb4720049d092905446876e714ce749a59d71f7f5b0d9bfdff5cff1424` |
| linux.config | 73073 | `11cec54e5bdda8a684086e340d0a9db4fa3509dbf1f779da669bd511042ea6fc` |
| rootfs.QEMU-ONLY.cpio.gz | 80519768 | `c21ef31056753abecb4d9cc6535a5cd906a6e73b32eaaede592502317e5725d1` |
| busybox.armhf | 808392 | `acf9bf52fcead11890b2f55cac7e6002cf8d8e88b8b025e68d154c9d8347dc6a` |
| container-resource-probe.armhf | 423640 | `aef3acf9201b0453eacd4724b6460fccf67c91a5fc2c54017cdf9e9faeccb333` |
| qemu.log | 21513 | `3e2cc709eb9cdd1ac74f8131d1c2872aa0ed7efc5127404895dfce81b4932d23` |

The uncompressed initramfs is 230579200 bytes. Its compressed size exceeds
the established physical router transfer budget. QEMU-only filenames, no
board DTB/uImage packaging, and distinct artifacts keep this output separate
from the physical RAM planner.

## Observed runtime checks

QEMU virt/cortex-a7 uses one CPU, 768 MiB, `-nic none`, no disks and no host
filesystem shares. Both guest init stages require the QEMU board identity and
explicit command-line gate before tests; all writes remain in guest RAM.
A real tmpfs root and upstream BusyBox switch_root let normal Docker/runc
pivot_root work, without DOCKER_RAMDISK or disabling pivot_root.

- Overlay2 and cgroup v2 are actual Docker info results. PID 1, requested
  hostname, ARMv7 architecture and seccomp mode 2 are checked in the container.
- The 64-MiB/0.5-CPU/32-PID container reads its exact cgroup limits. A fixed
  two-second CPU workload produces nonzero `nr_throttled`. This validates
  CPU throttling; the PID limit is read back, without a fork-limit stress claim.
- A separate 32-MiB container runs a bounded 64-MiB page-touch workload. The
  kernel reports `CONSTRAINT_MEMCG`; Docker reports exit 137 and OOMKilled.
  This is the intended cgroup OOM check, not a guest-wide memory exhaustion.
- Writable overlay data survives stop/start/restart and is absent from a fresh
  container. Lifecycle and HTTP service containers stop with exit 0.
- The guest clock alone reaches 2040. Writable-file mtime and the HTTP fixture
  file stat use the future timestamp. The physical board clock is unchanged.
- User-defined bridge containers resolve `service` through Docker's embedded
  127.0.0.11 resolver and fetch the exact fixture file across their real veth
  interfaces. An isolated external namespace accepts requests from both
  default and user-defined bridges; its CGI reports the masqueraded peer
  address. A request from that namespace reaches the published container port
  with Docker's userland proxy disabled, establishing DNAT/forwarding.
- Containers/networks are removed, the measured veth pair and external
  namespace disappear, and Docker/containerd complete normal daemon shutdown.
  All 11 required markers appear exactly once; the log contains no failure marker
  or kernel panic.

The isolated closure provides legacy `firewall` for `uci-firewall` and does
not run OpenWrt init, fw4 or Passwall. Guest-only routing demonstrates Docker's
IPv4 networking; Internet/registry DNS, IPv6, physical Ethernet forwarding,
fw4/Passwall interactions and production service budgets remain unverified.

## Regression and CI boundaries

The observed iptables-nft NAT startup failure was caused by missing NFT_NAT/
NFT_MASQ support. Selecting `kmod-nft-nat` supplies the actual modules; the
native compiled-config checker now rejects that missing dependency. The
reusable fixture also handles packaged nft alternatives, BusyBox's unnamed
veth peer and namespace teardown order, instead of assuming full iproute2.

Required `make lint`, `make build` and `make test` pass locally. The final
runtime's source hashes were independently compared with the Windows working
tree, every recorded output hash/length was verified, and its actual markers
and cgroup OOM record were checked. The updated CI workflow compiles native
packages then executes this separate isolated runtime test; fresh remote
runtime CI is pending, not claimed successful from configuration alone.

Physical eMMC blocks/ext4/shutdown/restart/backups, a storage-backed Docker
board candidate, fw4/Passwall composition, RDA firmware/STA/AP and final
routing remain required. The accepted native SD router remains online; its
second final return still waits for working UART reception. The full goal is
active/incomplete.
