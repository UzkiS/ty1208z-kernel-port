# eMMC 只读块源码与对象验证（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

2026-10-14. The explicit `HI3798MV100_EMMC_READ_ONLY` configuration compiles
real ARM objects and passes actual-function request/block-core checks. It has
no RAM boot image, partition/filesystem probe, shutdown/restart integration or
physical acceptance yet. No board reboot, card data/settings, persistent boot,
loader or security-state write was performed for these checks.

## Enforced request scope

The existing PIO/one-bit/25-MHz driver has a separate RO mode. It forces the
disk read-only callback and bounds requests to eight 512-byte sectors. Before
any request reaches card detection or the hardware queue, the actual card
must be MMC, sector-addressed, `008G30`, EXT_CSD revision 8 with 512-byte sectors,
exactly 15269888 sectors (7818182656 bytes), and selected to the user area.

CMD17/CMD18 require pure READ, exact native/SPI response/ADTC flags, one through
eight blocks and an in-range address. Multiblock reads require the exact
non-busy CMD12 sidecar; CMD23 is rejected. Standalone recovery CMD12 is limited
to zero argument and exact non-busy flags. Data writes, erase, partition
switching, boot/RPMB and unknown commands remain denied. Optional CMD6 settings
continue returning `-EBADMSG` without queueing; accepted identification
metadata remains available before card enumeration completes.

Both independent upstream block-core paths are suppressed only in this
configuration: `mmc_blk_alloc_parts()` creates no boot/GP/RPMB devices and
`mmc_blk_probe()` skips separate RPMB registration. The ordinary configuration
retains both paths. Clearing a userspace disk RO flag does not remove the
request-level barrier. The dedicated mode additionally refuses its driver
probe on a board identity other than `tianyi,ty1208z-ca-emmc-ro-ram`.

## Verified local results

- Repository lint, required diagnostic build, QEMU shell/time64 and serial
  integration gates passed. Future-clock tests ran only inside isolated QEMU.
- `test_emmc_ro.py` uses pinned Linux MMC command/request structures and actual
  overlay validator/slot plus patched DW request and block allocation/probe
  functions. ASan/UBSan runs cover all 64 opcodes, directions, block lengths,
  response flag bits, stop sidecars, end-of-card addresses, malformed requests,
  missing/wrong card identity, partition selections and both block-core modes.
- The same RO checks also pass with the fixed-sample macro enabled, confirming
  that its CMD17 allowance cannot bypass the RO card/user-area guard.
- Original identification/OCR callbacks and inherited DMA/IRQ handoff pass;
  the shared actual forced-RO callback still overrides GPIO/register state.
- Real selected Kconfig and DW host/MMC block objects compile for ARM. The
  existing metadata and fixed-sample profiles rebuild, pass exact DT/config
  mutation gates and pass their QEMU suites. All seven existing native SD
  Kconfig cases also pass after the new option is introduced.
- `make emmc-ro-compile` records checked ARM relocatable objects, configuration,
  actual-function log hashes and source identities. CI now invokes this target
  and the metadata builder invokes the RO regression; remote CI for this delta
  is pending until its pushed run is inspected.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `dw_mmc.o` | 26572 | `c47524fff64e0144f7feff5066427edc31de758ed8f5f50a864ae50be049ca09` |
| `dw_mmc-hi3798mv100-ident.o` | 7580 | `ab5b83eb7a4d4e524c792b31c0492b4bc91328c3fb9aa05db31933bfd278c5d8` |
| `block.o` | 28956 | `5b01d5b3df595f1677ae0d999de471cb8b23b8db782cd07ccb9071d9027b7db9` |
| `linux.config` | 40691 | `37fcca77773615f7d1096d37e26e62b5f4674434db2078e1c15dd6ae5e4e2afc` |

Generated/applied kernel patch SHA-256:
`e7b3373f75940979fe5857653e567a65c96ab78dcb89302d19a6974027af0c8a`.
The previously applied `ff49247d…` bytes were preserved and reversed before
generation; no newly generated patch was used to reverse the old source.

## Remaining acceptance

All eMMC block configurations are still denied by the RAM image/profile
planner. A complete distinct DTS/config/profile, verified host shutdown and
matched explicit restart support, partition/filesystem read probes, serial
gates and real board CRC/boot/return checks remain required before hardware
use. Ext4 reads must use `ro,noload`. Complete partition backups, integrity,
usable persistent Docker storage and actual containers remain unverified.
The current accepted Chinese SD router is unchanged; its final return awaits
host UART reception recovery.
