# USB host0 只读寄存器实测（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Date: 2026-10-13. The separate `usb-audit1` image booted from RAM through the
existing CA fastboot after fresh loader/DDR/command checks and matching host/
device CRC32. No control-register writes, USB transactions, firmware loading,
flash writes or persistent boot changes occurred.

| Item | Measured value |
|---|---|
| Kernel | `6.12.112-ty1208z-usb-audit1` |
| Image bytes / CRC32 | 2201344 / `aca7f04e` |
| Image SHA-256 | `391987d8831320d44bc96d4a4cc5e19660cafb6e8b0d18cca030b12e0519d8b2` |
| CRG46, `0xf8a220b8` | `0x0013707f` |
| CRG47, `0xf8a220bc` | `0x00000b01` |
| USB0, `0xf8a20120` | `0x000c71a8` |
| USB1, `0xf8a20124` | `0x00000000` |
| SYSID0, `0xf8000ee0` | `0x37980100` |
| SDK tuning branch | `(SYSID0 & 0xf0) != 0x10`, `sdk-other` |
| Capability reads | Skipped: inherited state not ready |

CRG46 retains controller reset bits 12–14 and 16–17. CRG47 retains PHY reset
bits 8, 9 and 11 and has only one of the required two reference-clock bits.
These do not satisfy the separately tested readiness predicate. The observer
therefore did not touch EHCI/OHCI capability registers, operational registers,
DMA schedules or endpoints. SYSID0 supplies the source's revision decision;
no fuse/OTP read was needed, and this is not an RDA Wi-Fi revision measurement.

The fixed UART collector verified the distinct kernel and complete read-only
audit markers. Shell, timer/IRQ diagnostics and the RAM-file time64 probe
completed with `sizeof(time_t)=8` and timestamp `2208988800` (2040). Raw logs
and transmit journals remain in ignored local evidence, with personal paths
and identifiers excluded from this report.

| Local evidence | SHA-256 |
|---|---|
| RAM transfer/boot stream | `9f07b9872d7b49ae250080ab3bb983c193de4dafe8643ea4d20b1b74eaab213f` |
| Fixed diagnostic collector stream | `86d989680d174d4cdc8dc693e4f0a7dfb8595da2c45624c01ce8c7b1e1f5ea4c` |

This establishes inherited controls and SYSID0 only. The ordinary USB host
RAM-boot gate remains closed because controller capabilities are still
unmeasured. A separate bounded clock/PHY initialization experiment must
establish those capabilities before the host profile is reviewed for boot.
EHCI/OHCI enumeration, RDA firmware/revision and radio operation remain
unverified. The narrow audit's source and offline checks are recorded in the
[offline report](usb-audit-offline-20261012.md).
