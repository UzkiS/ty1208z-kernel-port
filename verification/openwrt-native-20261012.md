# Native OpenWrt RAM target — initial software milestone

Date: 2026-10-12. No hardware transfer, flash or persistent configuration change.

## Fixed input

OpenWrt `58efa9917d4cc53fceed173529a286187649e827`, observed branch
`openwrt-25.12`, complete codeload archive:
`03f874336942999416a8c35fb2379f63b70e77a579f9b65b990471bc3d16730a`.
The source lock has no external feeds. Its Linux 6.12.112 and BusyBox 1.37.0
archive hashes match the separately tested board and stat-patch bases.

The independent `hi3798mv100` target has one `ty1208z_ca_ram` profile. It
inherits the UART/timer/CPU0 and bounded RAM description, uses Cortex-A7
NEON/VFPv4 hard-float musl, and defines an initramfs legacy uImage at the
measured `0x02000000` load/entry. No installation/sysupgrade image is defined.
Only loopback is configured; no storage, Ethernet or USB driver is selected.

## Observed local results

- Native OpenWrt metadata and `make defconfig` resolve the target, device,
  musl, gzip initramfs, installed time64 probe and BusyBox stat formatting.
- OpenWrt's complete generic backport/pending/hack 6.12 patch stack, followed
  by the authoritative board patch, applies to the fixed Linux archive.
- The generic-plus-target kernel configuration resolves the required board,
  timer, PL011 and appended-DTB options; SMP/BLOCK/MMC/MTD/USB remain disabled.
- The resulting native-profile DTB, board object and timer object compile
  with the existing system ARM compiler. This is a patch/config compatibility
  check, not an OpenWrt toolchain/ABI or full-image build result.
- All OpenWrt BusyBox patches followed by the existing stat time64 patch
  apply successfully to the fixed BusyBox archive.
- Repository lint, standalone diagnostic build, QEMU time64 and serial/RAM
  protocol regressions pass after the build directory ownership was repaired.

Local source-only patch audit logs are ignored. The complete native build
provides the reproducible image/toolchain verification; it is still running.
The separate OpenWrt GitHub workflow has been added; its actual result will
be recorded separately. No native image has been accepted by the physical
CA bootloader and no router/Passwall/Wi-Fi operation is claimed.

The complete-build gate checks resolved storage exclusions, image CRC/DTB
and decompression footprint before running the native initramfs kernel on
isolated QEMU virt. The guest test changes only the guest's clock to 2040
and exercises installed musl time64, BusyBox date/stat, UCI, procd/ubus and
logging. These checks are implemented but have not run to completion yet.
