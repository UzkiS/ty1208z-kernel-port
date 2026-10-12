# Native OpenWrt/Kwrt integration

The intended result is native OpenWrt with working Ethernet, optional onboard
Wi-Fi and Passwall. A new kernel and a successful RAM diagnostic are necessary
steps; neither is a working OpenWrt target or an installable image.

## Audited upstream state

The 2026-10-12 audit is pinned in
[`reference/openwrt-kwrt-audit.lock.json`](../reference/openwrt-kwrt-audit.lock.json):

| Repository | Observed branch | Audited commit |
|---|---|---|
| kiddin9/Kwrt | `25.12` | `d59e8be835f5a6ff9bfc2034ca14184c4b89b916` |
| openwrt/openwrt | `openwrt-25.12` | `58efa9917d4cc53fceed173529a286187649e827` |

Kwrt contains device customizations and a build workflow. Its common settings
point to the upstream OpenWrt repository, and its workflow selects a release
tag or the moving `openwrt-25.12` branch. The inspected device list has no
TY1208Z or Hi3798MV100 target. Upstream's inspected target list also has no
dedicated Hi3798MV100 target. `armsr` requires Arm SystemReady/EFI and is not a
drop-in target for the measured CA fastboot/uImage boot path.

The audited OpenWrt `target/linux/generic/kernel-6.12` selects **6.12.112**
with SHA-256
`164dc9d1f6c93c61a15e1f071c48379b467f2b17c469cce7223471968208ed03`,
matching this project's pinned upstream archive. OpenWrt still applies its
own generic patches and uses its own compiler/configuration. Matching the
base version does not make standalone modules ABI-compatible.

The Cortex-A7 CPU can use the existing OpenWrt CPU definitions
`CPU_TYPE:=cortex-a7`, `CPU_SUBTYPE:=neon-vfpv4`; the audited sunxi target is
evidence for these definitions, not compatible board support. Initial target
configuration must retain the measured boot/memory constraints and only
enable separately validated SoC peripherals.

## Source and build boundaries

Keep the native target/integration files separate from `overlay/` and
`wifi/overlay/`. Generate board patches from the authoritative Linux files,
then apply them to the fixed OpenWrt kernel and resolve generic-patch overlap
explicitly. Build the optional RDA driver as an external kernel package
against OpenWrt's prepared kernel; do not copy the standalone `.ko` into it.
Wi-Fi can be disabled while wired routing is being validated.

The audit manifest fixes the inspected files only. It is not a complete
build lock. Before a reproducible build, fix the OpenWrt and Kwrt commits,
all feed commits, required Kwrt modifications, package sources and hashes.
Kwrt's current common customization script references moving feeds, other
repositories and raw downloads. It has only been read, not executed. Translate
the needed customizations into reviewed, pinned integration steps.

Start with a native RAM root filesystem and fixed CA uImage loading. Provide
UART login, network configuration and minimal routing tools before adding
LuCI and application packages. Do not add sysupgrade installation support or
stock partition write actions until backups and recovery have been established
and the exact installation plan has session authorization.

## Passwall and Y2038 acceptance

Pin Passwall and its actual selected backend/transport/DNS dependencies as a
separate application layer. The user requires Passwall; the choice of engine
must be buildable on ARMv7 and validated under the board's measured memory
and network constraints. Package availability or an enabled LuCI option does
not establish an operational proxy path.

Use musl/time64 userspace from the fixed OpenWrt toolchain and test the built
artifacts. Validate the whole selected application set in an isolated ARM
QEMU guest with a 2040 wall clock: libc conversion, file timestamps, BusyBox,
logging, DNS, certificate validity, LuCI/rpcd and the chosen Passwall engine.
Exercise actual application start/configuration and data flow where emulation
allows it. The current diagnostic time64 probe alone does not cover these.

On the board, verify cold boot, DHCP/DNS, forwarding and firewall behavior,
Passwall traffic, reconnects, memory pressure and throughput. Include Wi-Fi
scan, association and AP only after its separate acceptance. Future wall-clock
testing remains confined to QEMU. Keep boot and runtime evidence separate from
software build results, and retain the existing CA bootloader and Hinas until
a later installation has been explicitly authorized.
