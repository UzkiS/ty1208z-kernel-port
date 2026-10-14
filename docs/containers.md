# Required Docker integration

Docker is a required feature of the final official OpenWrt system, alongside
Chinese LuCI, Passwall with Xray and sing-box, unzip and board Wi-Fi/AP support.
The [integrated native RAM system](../openwrt/system/README.md) now physically
runs a small ARMv7 container with overlay2, cgroup limits, default seccomp,
gateway DNS and TCP/HTTP through Ethernet. The exact runtime and safe return
are recorded in the [board report](../verification/openwrt-system-board-20261014.md).
Persistent Docker storage, final package registration and installation remain
unfinished. The earlier independent experiments below retain their original scope.
The board has 1 GiB of physical DDR and a 32-bit Cortex-A7/ARMv7 CPU. The
current RAM experiment intentionally exposes only the low 256 MiB, with the
low 16 MiB reserved. It is not a Docker installation candidate.
An independent [768-MiB memory experiment](ram.md) now passes physical 512-MiB
stress/PFN checks and autonomous return. Its independent native router768
integration now also physically passes memory/PFN, Ethernet/application and
automatic return checks; [native report](../verification/openwrt-router768-board-20261014.md).
Storage and actual Docker runtime acceptance remain separate.

Before integration, establish usable higher memory and independently validate
the eMMC driver, block I/O and filesystem/recovery plan. Storage installation
and persistent boot changes retain their separate authorization boundary.

Use pinned OpenWrt container packages and review their real dependencies:
cgroups/resource limits, namespaces, overlayfs, veth/bridge and netfilter.
Keep container bring-up separate from the existing diagnostic/router RAM
profiles until their measured memory and storage boundaries are satisfied.
Compiling Docker packages alone does not establish working container support.
The separate `make openwrt-container-packages TASKBASE=/absolute/linux/build-root`
entry now builds the official pinned Docker/dockerd 29.6.1, containerd 2.2.5,
runc 1.3.6 and tini 0.19.0 recipes under `TASKBASE/container-packages/`.
`openwrt/containers/sources.lock.json` pins the five recipe/source identities
against the same official packages feed. `make openwrt-container-config` only
resolves and checks their selection.

These packages are selected as `m`, separate from the application rootfs.
Their dependency kernel enables block support for upstream Btrfs dependencies,
namespaces, cgroups and seccomp, while MMC, MTD, USB, board Ethernet and SMP
stay excluded. The entry produces no rootfs/board image and refuses use by
the application QEMU or RAM packager. On successful compilation, the checker
extracts real APKs, checks ARM EABI5, verifies source/recipe hashes and runs only
`--version` through qemu-arm. It exports packages and provenance as compile-only
artifacts; no daemon or container is started by that check.
Clean remote compilation on `3e89e05` also passed; all 13 downloaded artifact
files, five package/source records, checker identities and actual version-check
marker were independently verified, [CI report](../verification/container-packages-ci-20261013.md).

The separate `make openwrt-container-qemu TASKBASE=/absolute/linux/build-root`
entry now tests those actual native packages in a Cortex-A7/ARMv7 QEMU guest
with 768 MiB, no NIC, disks or host mounts. Run `make build` and
`make openwrt-container-packages` first. Its BusyBox helper, deterministic local
Docker archive, complete APK dependency closure and exact kernel/config/input
hashes are recorded under `artifacts/openwrt-container-qemu/`.

Actual containers pass overlay2, PID/hostname isolation, default seccomp,
CPU throttling, memory-cgroup OOM enforcement, writable-layer persistence,
stop/start/restart and cleanup. User-defined bridge DNS/HTTP, default and
user-defined bridge masquerading, and published-port DNAT pass through another
guest-only network namespace. The daemon/containerd also shut down normally.
The clock reaches 2040 only inside the guest. The native package profile now
selects `kmod-nft-nat`: its absence previously prevented Docker's iptables-nft
backend from creating NAT chains; the compiled-config checker also rejects
that regression. [Runtime report](../verification/container-qemu-runtime-20261014.md).

These are QEMU-only outputs, separate from every board RAM candidate. They
exceed the existing physical router initrd transfer budget. The isolated
dependency closure provides legacy `firewall`; this experiment does not run
OpenWrt fw4 or Passwall, perform physical storage I/O or establish a final
router installation. Fresh remote runtime CI remains pending.

The independent `make openwrt-container-applications TASKBASE=/absolute/linux/build-root`
entry now builds the Chinese application rootfs, firewall4 and all five native
container cores from one source/kernel profile, runs the combined ARMv7 suite
at 768 MiB and exports verified QEMU-only delivery under
`artifacts/openwrt-container-applications-qemu/`. Its actual native `/init`,
BusyBox and procd are preserved. A separate gated fixture archive starts the
real dockerd service with guest-RAM storage and the real native tini. The
deterministic container includes that same rootfs's musl/libgcc libraries.

The combined suite passes overlay2, default seccomp, actual CPU throttling and
memory-cgroup OOM, PID-limit readback, embedded DNS, bridge masquerading and
published DNAT through real netifd/fw4 configuration. Both installed Passwall
cores also pass transparent TLS requests from an actual container network
namespace; native curl runs in that namespace. Direct requests fail before
and after each proxy. Docker networking survives the firewall and Passwall
reloads, and containers/network namespaces and the procd daemon shut down
cleanly. The original application checks still cover Chinese/empty-password
LuCI, both SOCKS/TLS cores, unzip, DNS/TLS and NTP/time64 across 2036/2038/2040.
All 26 required markers appear exactly once; input hashes are frozen before
preparation/runtime and verified afterwards. The exporter independently checks
native/core/kernel/fixture/console consistency and copied file hashes.
See [combined report](../verification/container-applications-qemu-20261014.md).

This profile has no CA/uImage, board DTB or installation path and is explicitly
refused by the physical RAM packager. It enables block support for declared
container dependencies while excluding MMC, MTD, USB, board Ethernet and SMP.
It is separate from the physically accepted SD router. Its workflow builds
from a fresh Linux checkout; a configured workflow is not successful CI
evidence. Physical storage-backed Docker, external Internet/registry access,
IPv6, performance and board integration remain pending.

Physical/final-router acceptance still needs a small `linux/arm/v7` container,
DNS and outbound/forwarded networking with fw4/Passwall, measured memory/CPU
limits and clean shutdown/restart. Confirm image architecture before download;
ARM64-only images cannot run natively on this CPU.

One GiB permits modest workloads; the current single-core experiment, storage
I/O, proxy load and actual free memory must determine the eventual service
budget. Physical Docker and full storage/final-router acceptance remain pending.

`tools/prepare_native_userspace.py` now prepares a RAM network-delivery
supplement from the accepted native archives without rebuilding or rerunning
applications. Fourteen application/runtime files are byte-identical between
the native eMMC and combined deliveries. The prepared 75-file supplement is
91123638 bytes compressed and excludes kernel modules and APK database state.
It is not installed or board-tested; the integrated board kernel must supply
its own modules, and final package registration remains to be integrated.
