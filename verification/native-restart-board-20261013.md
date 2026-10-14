# 原生 RAM 系统命令重启实测（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

2026-10-13: autonomous command restart and RAM-system return were tested.
One graceful native OpenWrt `reboot`
physically returned to Boot ROM/DDR training/CA Fastboot; the exclusive COM9
tool stopped autoboot and completed fresh read-only loader inspection. The
same router kernel/initrd then passed separate TFTP filesize/device-CRC gates,
booted again, restored 14 user files and empty root password, and reloaded the
restart module successfully. No user power cycle was needed for this sequence.

The initial strict SP805-ID module correctly refused registration: actual ID
cells were zero. A second observation established LOAD/VALUE `0xffffffff` and
CONTROL/RIS/MIS/LOCK zero. The original board/SDK FDT supplies an ID override;
the new module does not turn that override into a claimed hardware measurement.
Instead its explicit MV100 path checks measured SYSID0 `0x37980100`, zero ID
cells and that exact inactive register tuple at probe and again at restart.
Only the source-backed WDG0 unlock/disable/load/reset writes run in the callback.
Ordinary strict-ID diagnostic behavior remains unchanged.

## Exact physically used artifacts

| Artifact | Identity |
|---|---|
| Native router kernel uImage | 3437600 bytes, SHA-256 `b62240f15eedb72f28faaf2f2c03f5c985c62c40d19a140b8ebd63828a7c2ecd`, device CRC `3813a6ca` |
| Native rootfs | 33408575 bytes, SHA-256 `8c9d99caed2a11bc1a8e3fdd7da3164496ba834d6a556c9240f4ec30f253a0b1`, device CRC `32c0206d` |
| Loaded ARM module | 124080 bytes, SHA-256 `71b6c32364cbe07c360563c0a805ed9fc8eda982c677e2e06462abfec3782b8d` |
| Module-matching kernel config | SHA-256 `25c1ec112d9a6b31ec7c5057152021b508c935ac6e1113d5249e9ae4dd11104c` |
| Module-matching zImage | SHA-256 `45461a65f4f6e04b313beb60dc086480ffd880508f8c4dbf214cdb0acf1f04e0` |
| Restart UART stream | 16424 bytes, SHA-256 `37106777446a82d09e20a1bca6755cd2fc35a4cc01a02967264030cd5777a04a` |

The builder used the completed native GCC 14.3.0 toolchain and actual router
kernel symbols/configuration; the module reports `6.12.112 mod_unload ARMv7 p2v8`.
Actual helper mutations run under ASan/UBSan: wrong SoC, nonzero meaningful ID
bytes and any changed inactive register condition deny all reset writes. Actual
module init tests cover board denial, driver/device registration failure, failed
probe cleanup and device-before-driver removal. UART PTY checks cover both the
diagnostic and native paths, missing source/DT/module/guard, one-shot failure,
graceful native shutdown and fresh loader inspection.

## Limits

This module is RAM-only and explicitly scoped to the native router. New RAM
boots lose the module until it is loaded again. SD/eMMC/USB/Wi-Fi diagnostic
images still need matching restart integration; this result does not prove their
shutdown paths, cold-start operation, persistent boot or installation.
No card data, boot environment, bootloader, OTP/eFuse or security-state write was
sent by the host tools. The loader retained its original persistent boot command;
temporary TFTP network settings were restored before each kernel boot.
