# eMMC 用户区只读块实测（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

2026-10-14: the corrected independent low256 `emmc-ro1` RAM candidate passes
actual user-area block reads, all nine measured partitions, ext4 `ro,noload`
mount/file read/unmount and guarded command restart with verified controller
shutdown. The exact original Chinese OpenWrt and current configuration were
restored. No card-data, persistent boot/flash or security-state writes occurred.
This does not establish writable storage, a full backup or physical Docker.

## Exact corrected candidate

Linux 6.12.112, selected static ARM diagnostic userspace and the existing
low256/low16-reservation layout are reused. Kernel release is
`6.12.112-ty1208z-emmc-ro1`; DT identity is
`tianyi,ty1208z-ca-emmc-ro-ram`. Networking, modules, USB, SMP, PM and foreign
storage are disabled. The root filesystem and test files remain in RAM.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| uImage-UNTESTED.bin | 2908611 | `7203808ee3539a6a11fa02f39cb58a7cbe43944c4ab8e5f6a8fc4a6b62a3b8a1` |
| zImage | 2906288 | `b8dc3565848f5c7db34c6556c2d95962daf0efb7cf244293391b9731f407305f` |
| DTB | 2259 | `2ab267527d9db81a6cc7154707dad72cca31332a745de7a1850226d6e9f34f1f` |
| linux.config | 45190 | `ce3d0d8bfcc28e490a851c1d0861406efca41689df25af087b9e328bbf93866d` |
| initramfs.cpio | 1714176 | `b04568c4b65653772928dda215afa5dd97a3ede5931b233ae705f6bbbbb4b81b` |
| emmc-ro-probe.armhf | 429040 | `0b62b59f4def77f32d41519c3249a79d7c0e8f377e9f41dbf9e615bc021091b4` |

Generated/applied board patch:
`9de829b2cd37e9814efa22adb2142527fae87573803e5c73894f99802a8f941c`.
Physical BSS ends at 7018024, below 16 MiB. This payload has its own fresh
loader inspection, immutable TFTP receipt, size and independent device CRC;
the previous candidate's reception is not reused.

## Disk flag correction and measured protection

The first E848 candidate booted and identified the card/partitions, but the
userspace guard stopped before block probes because the whole disk reported
RO=0. MMC initialization derives its read-only state from card metadata; the
DW host's forced `get_ro()` callback alone does not establish the eMMC disk
flag. Request-level write denial remained in place. No filesystem mount or
block probe was attempted in that first failed test.

For the failed candidate's return only, the in-memory `force_ro` sysfs flag
was strengthened to 1 before the guarded restart. That sysfs operation sets
the kernel block flag and sends no card command. The failed candidate remains
unaccepted; its logs and original artifacts were preserved separately.

The generator now makes the actual `mmc_blk_readonly()` return true only for
this explicit configuration, so `md->read_only` and the initial disk state
are correct. Actual-function sanitizers cover writable/read-only card metadata,
missing write support, both profile states and real `force_ro_store()` clear,
set and malformed-input cases. The old applied source fails the new regression;
the corrected source passes. Ordinary MMC behavior is preserved with the
configuration disabled.

The exact card is `008G30`, manufacturer `0x11`, EXT_CSD rev 8, 15269888 sectors,
7818182656 bytes (7.28 GiB). Controller is `f9830000`, DW `0x270a`, 32-bit FIFO,
inherited 100-MHz source; transfers use PIO/one-bit/legacy/25 MHz. The corrected
native disk and all nine partitions report RO=1. Boot0, boot1 and RPMB nodes
remain suppressed; only the measured ten user-area block nodes exist.

Protection remains independent at the request queue: writes, erase, CMD6
settings, CMD23, partition switching and malformed/out-of-range reads are
denied before hardware queueing. Accepted sector reads are bounded to eight
512-byte sectors, with exact nonbusy STOP sidecars. No deliberate physical
write request or card-setting write was used as a test.

## Actual reads and cleanup

All nine partition starts/sizes match the measured original layout. Actual
4096-byte reads, 1024-byte overlapping comparison, final 4096-byte read and EOF
checks pass. The original Hinas header sector matches CRC32 `2ba1a125` and its
ordinary uImage load/entry. The root partition's ext4 magic and 4096-byte block
size match.

Partition 9 mounts with `ro,noload`; the kernel confirms read-only operation
without journal replay. One existing nonempty file yields a bounded 444-byte
read. Its name/content, UUID and card serial are excluded from this report.
The mount and RAM directory are removed. IRQ Err stays zero; the RAM-file
time64 probe passes without changing the physical wall clock.

Initial direct console output was split by asynchronous ext4 printk during
unmount, so the strict CLI correctly rejected that capture. The collector now
buffers userspace output under RAM `/tmp` until the filesystem has unmounted,
then emits and removes the report. The final exact CLI capture contains every
required marker intact and passes; validation is not relaxed to accept broken
markers. Earlier incomplete captures remain separate failed observations.

## Shutdown, return and remaining work

One guarded `reboot -f` verifies exact release/DT/restart binding, unmounted
state, RO=1, capacity and restart registration. The actual stream contains
`EMMC_RO_SHUTDOWN_COMPLETE host-removed clock-disabled no-card-writes`, then
fresh original CA-loader output and completed inspection. No reset retry or
manual power cycle is used. The exact original router's two device CRCs and
current configuration/account/key hashes are verified after return. Chinese
authenticated Passwall UI, empty root login, restart binding and IRQ Err0 pass.
COM9 is released.

Local `make build`, `make lint`, `make test`, `make test-serial`, `make emmc-ro`
and `make emmc-ro-compile` pass, including the new disk-flag regression, actual
guest/probe/policy/shutdown/reset checks and generic QEMU. The preceding E848
diagnostic CI is independently verified in the [CI report](emmc-ro-ci-20261014.md);
fresh clean CI for this correction remains pending.

Full host backups, sustained/storage performance, native OpenWrt eMMC
integration, writable storage and storage-backed Docker remain separate work.
RDA firmware/STA/AP, external routing and persistent installation are also
unfinished. Installation still requires its later layout/backup/recovery
review and session authorization.
