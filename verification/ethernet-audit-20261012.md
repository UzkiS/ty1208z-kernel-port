# 网口继承寄存器状态实测（2026-10-12）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Date: 2026-10-12. The installed CA fastboot and Hinas remain unchanged.
No flashing, persistent environment, clock/reset, PHY register, DMA,
storage or OTP/eFuse writes were performed by this profile.

## Candidate and validation

| Item | Value |
|---|---|
| Kernel | `6.12.112-ty1208z-ethernet-audit1` |
| uImage bytes | 2201364 |
| uImage SHA-256 | `b96f467eef655a1fe1f9a8534120e7be633a9a6209887e9d83ab3d90ddf6ec08` |
| Host/device transfer CRC32 | `dd2d95d9` |
| Physical BSS end | `0x005adde8` |

Local standalone build, lint, bounded MDIO helper ASan/UBSan tests,
DT/config/image/placement checks and QEMU time64 passed. Serial regressions
exercise each profile's actual markers separately. The Ethernet collector
initially required an eMMC-only `BLOCK_DISABLED` marker; that host-side error
was corrected and the same running kernel was recollected successfully.
Subsystem exclusion is checked from the exact artifact configuration.

## Measured result

The CA bootloader accepted the RAM image, its CRC matched, and Linux reached
the diagnostic shell. The driver observed:

```text
ETH_AUDIT CRG51=00000003
ETH_AUDIT PHY_CRG=00000101
ETH_AUDIT PHY_SELECT=0e000004
ETH_AUDIT PHY_ADDRESS=03000001
ETH_AUDIT PHY_LDO=00000008
ETH_AUDIT_MDIO_SKIPPED inherited-state-not-ready
ETH_AUDIT_COMPLETE no-phy-writes no-clock-reset-writes no-dma
```

CRG51 lacks bit 3 of the SDK's mask/value `0x000b`. The internal PHY's
clock/reset/selection/address fields meet this audit's other conditions.
The gate therefore skipped every MAC and MDIO access. No PHY ID was read.
The observed LDO is `0x8`; the SDK MV100 fallback writes `0x68`, so copying
its initialization sequence would change a second unverified board condition.

The guarded CLI returned `diagnostic-captured`. Timer IRQ increased
45944 -> 46046 over uptime 459.37 -> 460.37 seconds, UART IRQ increased
1055 -> 1322, and interrupt errors remained zero. MemTotal was 244476 KiB.
`time_t` was eight bytes and a RAM-file timestamp round-tripped
`2208988800` / `2040-01-01T00:00:00Z`; the board wall clock was not changed.

## Evidence and limits

| Local record | SHA-256 |
|---|---|
| `ram-boot-20261012T115709.632368Z.rx` | `a9e97ecb0b072dc8c11dc55c0be3aed01ffa18ae720d2420befe8f73cbbad2ce` |
| `board-diag-20261012T120825.193990Z.rx` | `1f3314a00929f60a4c3be69ee26915183fc92a28321695a21a3ff385dcfdf727` |

These results establish an inherited-state observation and a functioning
RAM diagnostic, not working Ethernet, a PHY model, clock frequency or a
complete cold-start sequence. A separate candidate must validate any
volatile clock change before PHY identification. Link, packet/DMA/IRQ,
routing, performance and Wi-Fi acceptance remain pending.
