# 继承 PHY 的有线数据通路实测（2026-10-12）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Date: 2026-10-12. The TY1208Z CA ran the single-core, low-256-MiB RAM
candidate `6.12.112-ty1208z-ethernet-net1`. Installed Hinas, CA fastboot,
boot environment, storage and OTP were not changed. Storage/USB/modules/SMP
are disabled and the root filesystem is in RAM.

## Image and implementation

The booted uImage is 2900564 bytes, SHA-256
`0f17565d666fd52833fbe84f5fc29cccec58744a73c876e660cf896bbc5d44c4`,
CRC32 `66ead73b`. Its zImage SHA-256 is
`3906a9c4a02ca8b4a17b6343765aa17860428950d59d2b249754cda8b0b6ee29`;
expanded Image SHA-256 is
`ddaa9f3056393e671f41c10f0003138c82a6c1a463f408ea36f414325f88bc73`.
Physical BSS ends at `0x006b7a20`, below the 16-MiB allocation reservation.
Host/device CRC matched before the existing CA bootloader accepted the
ordinary unsigned RAM image.

This image contains the TX-monitor/NAPI correction after `f60474c`: masked
TX-ready status cannot claim the shared interrupt, RX descriptors remain
pending until consumed, TX-ready is armed on exhausted credits only, and a
20-ms monitor schedules bounded reclamation. The actual extracted patched
functions pass ASan/UBSan regression. See [offline checks](ethernet-net-offline-20261012.md).

## Measurements

| Check | Observed result |
|---|---|
| Clock and PHY binding | CRG51 `0x0000000b`; exact inherited-state guard passed; dedicated FESTAv220 driver verified PHY `0x20669823` at address 1 |
| Link | 100 Mbps full duplex, pause disabled |
| DHCP | Lease acquired with default gateway; local addresses omitted |
| Gateway reachability | Four successful ping replies using the image's simple ping applet |
| Host MTU test | Windows IPv4 ping, 1472-byte payload with DF: 20/20 replies, zero loss; min/max/average 3/15/6 ms |
| Interface reopen | Three software down/up cycles; each regained link and gateway reachability |
| Final counters | RX 82 packets / 36679 bytes; TX 46 packets / 32814 bytes; RX/TX errors and drops zero |
| IRQ | MAC GIC hardware IRQ 103 (SPI 71) count 82; global Err=0 |
| Generic board diagnostics | UART input/output, timer progress and RAM-file time64 passed; MemTotal 244472 KiB |

The first DHCP operation acquired a lease but its final ping command failed
because the initial BusyBox omitted fancy ping and did not support `-I`.
The CLI correctly recorded that operation as an error. The fixed, bounded
simple-ping command subsequently passed without another boot. Updated
BusyBox tooling now enables fancy ping and checks actual ARM `ping --help`
during the build; that later tooling image has not been booted physically.

## Local evidence identities

Raw logs remain in ignored local evidence and contain network identities.
Published observations omit MAC addresses, local IPs and personal paths.

| Capture (UTC timestamp) | Raw receive SHA-256 |
|---|---|
| RAM boot `20261012T134819.750692Z` | `2c2dbf63fbb9c0cebf86dfbcc2be6dad0e955bb204c1adf8b7332e78184ebc70` |
| Board diagnostics `20261012T135412.325301Z` | `4fd63871ff0590cd82467d99c7c3aceb9d13e9221b52f1aa9a3f67b46ce3d0a1` |
| DHCP with unsupported ping `20261012T135459.390910Z` | `caccebe1ea89b08e67c3fd7eb97ab7614244c7e4cd5d74eaeee7050d1dd74db7` |
| Completed gateway ping `20261012T135710.810097Z` | `aefa3b118f9461431b6a7c4e2025bf602ff9a768c4a2880324d0632388b7eaf9` |
| Interface cycles `20261012T135835.228794Z` | `c78a768ef1b037095e4aa6c50e3585ac4d0a3953c2506a7754b7d4abad87d483` |

The host MTU command was `ping.exe -n 20 -w 1000 -l 1472 -f <board-address>`.
Its terminal result was observed; it was not saved as a separate raw file.

## Limits and next acceptance

These results establish basic MAC/PHY/IRQ/DMA operation with state inherited
from the preserved CA bootloader. They do not establish independent PHY
cold-start initialization, physical cable removal/reconnection, sustained
TCP throughput, checksum behavior under load, native OpenWrt networking,
Passwall routing performance or an installable image. Those need separate
measurements. No flashing or persistent boot changes were performed.
