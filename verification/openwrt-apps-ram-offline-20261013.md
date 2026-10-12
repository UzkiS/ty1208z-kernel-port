# Native application external-initrd RAM candidate — 2026-10-13

Result: the exact native OpenWrt application kernel/rootfs passes the full
application fixture with a 240-MiB usable QEMU memory cap. A separate ordinary
uImage/DTB wrapper and bounded external initrd are packaged and pass the RAM
planning and UART fail-closed checks. **No physical transfer or boot of this
candidate has occurred.** It is not a working router or an installable image.

## Exact local identities

| File | Bytes | SHA-256 |
|---|---:|---|
| Raw zImage | 3390152 | `4f4c44b7d59b2691a51c56aed552c15cbe590e56f82827b8ec77bdbd721ae7c1` |
| Wrapped uImage | 3391924 | `c755bb3348590b284038f898f498ba254845af7e70e4d0ef2d90706a3a9403e5` |
| Board DTB | 1708 | `3522cb1374ae75a18af5a7af3d2280bd92050b1d6b263dce7bf5085d0bde881f` |
| rootfs.cpio.gz | 20925068 | `526cbe67000e957430746aa56300ac65705d4522120a4f01a4608d42e654d338` |
| Kernel config | 63584 | `a8582e03e71a4d7d738149fecc6ae77716ef9e9c876363ba3d5b13967705f61f` |
| Package manifest | 4344 | `d29c82e50d81d5e8d2cca567bc79ec99b3edce7740bd4a5623d43cdfc173e539` |
| 240-MiB QEMU console | 30896 | `2301452cbfa8b929976ff21b3b93c16ae37ac93e041758232393c076902d4f70` |

The kernel release is `6.12.112-ty1208z-openwrt-ram`. Modules come from the
same native application build. The wrapper changes only the appended board
DTB and uImage packaging; it does not rebuild/copy in different kernel modules.

## Placement

- Kernel header/payload/entry reuse the measured original path:
  `0x01ffffc0` / `0x02000000` / `0x02000000`.
- Decompressed kernel begins at `0x00008000`; BSS ends at `0x009beac0`, below
  the reserved low-16-MiB allocation boundary.
- Compressed initrd occupies `0x04000000..0x053f4a8c` (end exclusive), separate
  from kernel transfer/decompressor workspace. Its uncompressed newc archive
  is 53926400 bytes; budgets are 32 MiB compressed and 96 MiB uncompressed.
- Even the maximum compressed range ends below the original bootloader's
  unexplained Bound Addr `0x08e62000`. An earlier offline 128-MiB placement
  crossed that value and was replaced before any hardware transfer. The meaning
  of the field and a complete memory/reservation map remain unresolved.
- The DTB still limits memory to the low 256 MiB, reserves low 16 MiB and exposes
  only CPU0/UART/GIC/timer. It adds no board Ethernet, storage, USB or restart.

The guarded plan made from the actual recorded CA loader inspection has uImage
CRC32 `d2d22862` and initrd CRC32 `9a102b17`. Both device CRCs are required before
boot. No persistent environment, flash or security writes are part of this flow.

## Completed checks

The actual ARM application fixture passed on QEMU virt, Cortex-A7, one CPU,
`-m 256M` and `mem=240M`, with no disk or host networking and an isolated 2040
clock. The markers cover real DNS, OpenSSL/curl TLS (including certificate
rejection), authenticated LuCI/Passwall/rpcd, actual Passwall-generated Xray
SOCKS and VLESS TLS traffic, nft packet counters and socket/TPROXY expression
acceptance. The original 512-MiB acceptance remains a separate record.

The package gate ties the actual kernel/config/rootfs/packages/console hashes
to that memory/clock acceptance and verifies the critical board C/timer source
files against the authoritative overlay. CRC/header/DT/layout inspection and
the guarded plan against the actual raw loader report passed locally. Five
tests exercise the actual candidate, resource/config/provenance mutations,
unapproved transfer commands/addresses and both CRC failures through a serial
PTY. Either failed CRC sends no boot command; both matching CRCs boot once.

`make lint`, serial checks, `make build` and `make test` passed after the change,
including the ordinary single-image CRC/DDR serial regressions and core QEMU
time64. The application workflow now invokes `make openwrt-app-ram`, performs
both memory trials and uploads a separate HARDWARE-UNTESTED artifact. Its new
run has not yet established CI acceptance for this change.

## Remaining hardware gates

QEMU does not prove MV100 RAM placement, CA acceptance, UART/interrupt/timer
operation or physical rootfs expansion. This application profile has no board
network driver, so it cannot establish routing or Passwall TPROXY on hardware.
The native Ethernet candidate remains the next scheduled physical boot. It
needs its own sustained TCP and recovery measurements before integration.
USB/RDA firmware/radio, full RAM/SMP, Hinas startup, persistent storage and
whole-system Y2038 remain unfinished.
