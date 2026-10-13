# Required Docker integration

Docker is a required feature of the final official OpenWrt system, alongside
Chinese LuCI, Passwall with Xray and sing-box, unzip and board Wi-Fi/AP support.
The board has 1 GiB of physical DDR and a 32-bit Cortex-A7/ARMv7 CPU. The
current RAM experiment intentionally exposes only the low 256 MiB, with the
low 16 MiB reserved. It is not a Docker installation candidate.
An independent [768-MiB memory experiment](ram.md) now passes physical 512-MiB
stress/PFN checks and autonomous return. Later native-router integration is separate.

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

First acceptance should run one small `linux/arm/v7` container, exercise DNS
and outbound/forwarded networking with fw4/Passwall, verify memory/CPU limits
and clean shutdown/restart. Confirm image architecture before download;
ARM64-only images cannot run natively on this CPU.

One GiB permits modest workloads; the current single-core experiment, storage
I/O, proxy load and actual free memory must determine the eventual service
budget. Docker and full-memory/storage acceptance remain pending.
