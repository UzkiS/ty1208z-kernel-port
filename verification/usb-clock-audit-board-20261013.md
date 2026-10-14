# USB 时钟、能力与关闭实测（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Date: 2026-10-13. The independent `usb-clock-audit1` image completed a physical
RAM boot on TY1208Z. No persistent boot/storage changes were made.

The exact 2200676-byte uImage SHA-256 is
`365f8711150fd474d5d73ce929975b175427ba36a2d4e6c96108f539889abecf`.
Fresh bootloader inspection, immutable TFTP receipt and device CRC32
`25765904` passed; original loader network settings were restored before boot.

| Measurement | Actual value |
|---|---|
| Initial CRG46 / CRG47 | `0013707f` / `00000b01` |
| Initial USB0 / USB1 / SYSID0 | `000c71a8` / `00000000` / `37980100` |
| EHCI CAPBASE | `01000010`: 16-byte capability header, EHCI 1.0 |
| EHCI HCSPARAMS / HCCPARAMS | `00001212` / `0000a026` |
| OHCI revision | `00000110`: OHCI 1.0, legacy-support bit set |
| Stopped CRG46 / CRG47 | `0010000e` / `00000f03` |
| Stopped USB0 / USB1 | `000c71a8` / `0000a801` |
| Stop error | `0` |

HCSPARAMS reports two ports and a companion-controller arrangement. HCCPARAMS
does not advertise 64-bit DMA. The addresses and capability-header offset agree
with the prepared generic EHCI/OHCI host0 profile. The measured SYSID0 selects
the helper's non-`0x10` tuning branch. All four required clock-audit markers
appear in the physical boot and later complete diagnostic capture.

The complete diagnostic reports 244476 KiB MemTotal. CPU0 timer interrupts
increase from 17773 to 17874 over one second, UART interrupts increase from
1064 to 1353 and GIC errors remain zero. The RAM-file probe reads back
`2208988800` with eight-byte `time_t`. No future wall clock was set.

The first full diagnostic capture stopped partway through output. Reconnecting
only the TTL adapter restored reception; a fresh collector run verified the
kernel identity and complete report. Raw evidence remains local and ignored.

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| Fresh bootloader inspection | 2491 | `9669c93e444d69dc4b332653fc9c93e45584a2ab2a3166c915c25dc88337aa5f` |
| TFTP/boot console | 9002 | `b13a41323e5e0ec624ea73c8fdb01d7064e9a0359c7741b3c25801f67db8669f` |
| Complete diagnostic | 7790 | `5dcc4da3eb330a5972663267f3d1a0c7293719662cd5fe193355dd985003e1e0` |

This establishes volatile initialization, bounded capability reads and SDK
last-user shutdown. Analog tuning is not restored. It does not establish USB
device transactions, DMA, companion lifetime, firmware or Wi-Fi STA/AP.
Following review, the RAM planner now accepts only the existing exact
`usb-host1` enumeration profile, retaining its resource/config/layout checks.
Ordinary diagnostic/network/router images gain no USB permission.
