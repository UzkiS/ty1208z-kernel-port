# 独立 eMMC 只读 RAM 候选（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

2026-10-14: the separate `emmc-ro1` kernel, RAM userspace, measured partitions,
ext4 `ro,noload` probe and guarded restart pass local offline checks. This
report records the original E848 offline payload. Its subsequent physical boot
stopped before block probes because the disk RO flag was missing. The corrected
payload and later physical results are recorded separately in the
[board report](emmc-ro-board-20261014.md). This original offline build does not
establish an eMMC backup, writable storage, Hinas startup, Docker or installation.
The [object-only milestone](emmc-ro-offline-20261014.md) retains its own
source/artifact identities; its manifests were not rehashed against this source.

## Exact build and isolation

Linux 6.12.112, pinned diagnostic toolchain/BusyBox and low256 RAM are reused.
Root identity is `tianyi,ty1208z-ca-emmc-ro-ram`; release is
`6.12.112-ty1208z-emmc-ro1`. Root stays in RAM through `/init`. The exact
DT/config validator denies networking, modules, USB, SMP, PM and foreign
storage/reset/filesystems. Temporary DT bootargs supply the measured nine
user-area partitions without changing a table or persistent boot environment.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| uImage-UNTESTED.bin | 2908619 | `f41e8dc387d6d89706f9a382d242a29d059c9ed3f823d0f84c76b988bfd6d842` |
| zImage | 2906296 | `8a4cfd9cb7cf7b64fc4bc1ed483a7fe1d97f6d69e2891081d93c862fc10e737a` |
| DTB | 2259 | `2ab267527d9db81a6cc7154707dad72cca31332a745de7a1850226d6e9f34f1f` |
| initramfs.cpio | 1714176 | `b04568c4b65653772928dda215afa5dd97a3ede5931b233ae705f6bbbbb4b81b` |
| emmc-ro-probe.armhf | 429040 | `0b62b59f4def77f32d41519c3249a79d7c0e8f377e9f41dbf9e615bc021091b4` |
| linux.config | 45190 | `ce3d0d8bfcc28e490a851c1d0861406efca41689df25af087b9e328bbf93866d` |

Generated/applied patch SHA-256:
`e8487bf7ba471700e0604d790454c22912e37445b12e625800118b99844638f7`.
The actual preceding E7 and intermediate E265 patches were saved and reversed
before regeneration. The final payload was rebuilt after real ARM-shell
integration caught missing arithmetic support and the reserved awk `index`
name. The script uses existing applets; base BusyBox defaults did not change.
Physical BSS ends at 7018024, below low16MiB. Actual CRC, appended DTB,
static ARM ELF, configuration and bounded RAM-plan mutation checks pass.
Physical boot still requires fresh loader inspection and device CRC.

## Read and shutdown behavior

The [existing RO policy](emmc-ro-offline-20261014.md) remains enforced at the
DW request queue and block core. Only the measured 7818182656-byte user area
is exposed; physical boot0/boot1/RPMB nodes are suppressed. Reads use at most
eight 512-byte blocks and an exact nonbusy STOP. CMD23, card settings changes,
writes, erase and partition switching remain denied.

The userspace probe uses read-only opens, no symlink following and nonmutating
ioctls. It verifies major/minor, RO and capacity, then first/overlap/last/EOF
reads, the measured Hinas header sector CRC and ordinary header/load/entry,
and ext4 superblock. The guest checks all nine starts/sizes and exactly ten
block nodes, mounts p9 with `ro,noload`, reads a bounded nonempty file without
publishing its name/content and cleans the mount/RAM directory after success
or failure. Tests use a synthetic header, not copied firmware bytes.

Shutdown stops/removes the DW host and checks IRQ masks, clock enable, DMA
and IDMAC state. The independent reset callback repeats measured controller/
CRG identity and quiescence before dispatching the accepted MV100 watchdog
helper. Watchdog/SYSID resources are exclusive; controller/CRG are read-only
shared observations of resources owned by the eMMC driver. Reset probe makes
no startup writes.

The UART profile requires exact release/DT/binding, unmounted/cleaned RO
user-area state and measured restart registration. It sends one `reboot -f`
from the RAM shell, requires actual shutdown completion and fresh CA loader
inspection, rejects shutdown/reset failure and never retries reset. This new
path has offline PTY acceptance only.

## Validation and physical boundary

Local `make lint`, `make build`, `make test`, `make test-serial` and final
`make emmc-ro` pass. Actual policy/slot/block-core, driver shutdown, restart
callback and userspace probe run under ASan/UBSan. Selected ARM BusyBox runs
the actual guest against synthetic sysfs, checking board/RO/capacity/layout/
extra-area denial, exact mount arguments and failure cleanup. Real PTY cases
cover diagnostic content/capacity/cleanup and restart identity/binding/RO/
capacity/mount/cleanup/missing-shutdown/failed-shutdown/reset-refusal. The same
raw kernel/initramfs pass isolated generic QEMU time64 checks. QEMU does not
emulate the physical MV100 controller, card or watchdog.

After user TTL reconnection, actual UART reception and interactive input
recovered. The second native SD trial completed a guarded command restart,
verified controller shutdown, fresh CA-loader inspection and the exact
original low256 router's two device CRCs. Current configuration, Chinese
authenticated LuCI, empty root login, restart binding and IRQ Err0 pass after
return. The subsequent eMMC experiment and disk-flag correction have their own
fresh loader/CRC and physical observations in the [board report](emmc-ro-board-20261014.md).
