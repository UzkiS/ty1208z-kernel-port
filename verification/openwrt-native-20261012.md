# Native OpenWrt RAM target — local build and QEMU acceptance

Date: 2026-10-12. No hardware transfer, flash or persistent configuration change.

## Fixed input

OpenWrt `58efa9917d4cc53fceed173529a286187649e827`, observed branch
`openwrt-25.12`, complete codeload archive:
`03f874336942999416a8c35fb2379f63b70e77a579f9b65b990471bc3d16730a`.
The source lock has no external feeds. Its Linux 6.12.112 and BusyBox 1.37.0
archive hashes match the separately tested board and stat-patch bases.

The independent `hi3798mv100/ram` target has one `ty1208z_ca_ram` profile. It
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

The complete native build now passes locally with GCC 14.3.0 and musl 1.2.5.
The target configuration was completed through OpenWrt's own kernel config
update workflow, with explicit little-endian ARM and gzip kernel compression.
An explicit `ram` subtarget resolves device-profile image selection. Archive
build metadata records the actual source commit, uses local package revision
1 and passes a fixed epoch to make; the APK `unknown` version fallback is not used.

The separate OpenWrt GitHub workflow passed on commit `99bdd88`:
[run 38230366184](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38230366184).
It performed a clean native build and the core QEMU tests. Later storage and
application changes are outside that run. No native
image has been accepted by the physical
CA bootloader and no router/Passwall/Wi-Fi operation is claimed.

The complete-build gate checks resolved storage exclusions, image CRC/DTB
and decompression footprint before running the native initramfs kernel on
isolated QEMU virt. The guest test changes only the guest's clock to 2040
and exercises installed musl time64, BusyBox date/stat, UCI, procd/ubus and
logging. All pass using the actual native initramfs kernel. Console activation
waits for askfirst's TTY setup, and the logging check waits for `/dev/log`
before issuing a test message, rather than treating an early login as completed
service startup.

```text
TIME64_PASS sizeof(time_t)=8 realtime=2208988800 file=2208988800
Sun Jan  1 00:00:00 2040 user.notice time64: OPENWRT_LOG_2040
OPENWRT_RAM_QEMU_PASS
```

## Exact local artifact

| Item | Value |
|---|---|
| CA initramfs uImage bytes | 4983380 |
| uImage SHA-256 | `6b90eb6c663d3b02fb091ccca2642e0a4751aba792cafd097fbba59c7e5ba794` |
| Raw zImage SHA-256 | `fcf60d0f516b8797fc3298ff85143fe9002711bb5994c7aff8b69c0185eb3e00` |
| Physical image/BSS end | `0x00988100` / `0x009be280`, both below 16 MiB |
| Rootfs cpio.gz SHA-256 | `6e9957026eb990228ff7586b8423605397b664f3e2229646faf9e02724b16f49` |

The artifact remains HARDWARE-UNTESTED and is excluded from Git. QEMU uses
virt's DTB, not the MV100 appended DTB. Storage, Ethernet, Wi-Fi, LuCI/rpcd,
DNS/proxy/certificate flows and whole-system application Y2038 acceptance
remain outside this bring-up result.
