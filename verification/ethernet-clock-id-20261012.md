# 网口临时时钟与 PHY-ID 实测（2026-10-12）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Date: 2026-10-12. The CA fastboot and Hinas remain unchanged.
No flashing, persistent environment, PHY register/reset, DMA, storage or
OTP/eFuse writes were performed. This profile does make volatile MAC clock
writes and MDIO controller read-command writes.

## Exact candidate and local gates

| Item | Value |
|---|---|
| Kernel | `6.12.112-ty1208z-ethernet-clock-id1` |
| uImage bytes | 2201512 |
| uImage SHA-256 | `23e1db463ff1d16aeee7b02a7be0a9a3d77c198941f8db27e02ca914f8171204` |
| Host/device CRC32 | `9d4420a0` |
| Physical BSS end | `0x005adde8` |

Standalone build, lint, serial/RAM integration, DT/config/image/decompression
gates and QEMU time64 passed. The actual helper runs with an MMIO seam under
ASan/UBSan: all 160 single-bit control-state changes are rejected without
writes; fixed clock/MDIO command values, every busy timeout, absent IDs and
unexpected enable/restoration state are checked. ARM rejects a constant
5-ms `udelay`; the candidate uses the kernel's `mdelay(5)` instead.

## Physical acceptance

The CA bootloader accepted the ordinary RAM image after size and CRC checks.
The kernel reached its diagnostic shell and reported:

```text
ETH_CLOCK_ID CRG51=00000003
ETH_CLOCK_ID PHY_CRG=00000101
ETH_CLOCK_ID PHY_SELECT=0e000004
ETH_CLOCK_ID PHY_ADDRESS=03000001
ETH_CLOCK_ID PHY_LDO=00000008
ETH_CLOCK_ID_STATE before=00000003 enabled=0000000b restored=00000003 changed=1 verified=1
ETH_CLOCK_ID_PHY_ID=20669823 addr=1
ETH_CLOCK_ID_COMPLETE clock-restored no-phy-reset-writes no-dma
```

PHY ID `0x20669823` matches **FESTAv220** in the pinned SDK
`include/linux/hisilicon_phy.h`; that header uses mask `0xfffffff0`.
No generic PHY state machine or vendor PHY fixup ran. This confirms bounded
MDIO identification after temporary bit-3 enable and verified restoration.

The guarded CLI returned `diagnostic-captured`. Timer IRQ increased
7473 -> 7575 over uptime 74.69 -> 75.70 seconds, UART IRQ increased
106 -> 375, and interrupt errors stayed zero. MemTotal was 244480 KiB.
RAM-file time64 passed with eight-byte `time_t`, timestamp `2208988800`
and conversion `2040-01-01T00:00:00Z`. Wall time was not changed.

## Evidence and remaining work

| Local record | SHA-256 |
|---|---|
| `ram-boot-20261012T124039.119085Z.rx` | `e52c3ffbd1e8ffae2b0653d8d3de153d828fe658ef72f988aa729220ed9de8f4` |
| `board-diag-20261012T124530.522587Z.rx` | `f480bd46434fe0b69e06c9ad6165afa443ce87ae814e991c1eae7227676b70c6` |

Clock frequency, complete SoC/PHY cold-start, vendor volatile PHY fixups,
MAC/DMA/IRQ integration, link/traffic/routing/performance and Wi-Fi remain
unverified. Identifying the PHY is not working Ethernet. The box currently
runs this RAM diagnostic; no network or working soft-restart handler is
integrated. The installed Hinas remains on eMMC.
