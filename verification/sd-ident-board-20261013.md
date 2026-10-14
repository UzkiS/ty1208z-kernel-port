# SD 卡识别与自动返回（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Date: 2026-10-13 UTC. The separate `sd-ident1` RAM image identified the
inserted SDHC card, then command reboot returned through the original CA loader
to the exact Chinese native OpenWrt router without a manual power cycle.
No sectors were read, filesystems mounted, card data written, persistent boot
settings changed or security-state writes performed.

## Exact image and placement

| Payload | Bytes | SHA-256 |
|---|---:|---|
| uImage | 2252642 | `2a8880a9842f2705df04088bba533dee726ee837fb44313eccc5835790ea952c` |
| zImage | 2250496 | `99ed1a7cfc4d5d74ed198d9fa88c8085680e45ad6bbabee191d6a49d014d13a1` |
| DTB | 2082 | `ff448274eaeaf8897099a5ded1fdc810844ba0efddc03fcafd8adc74a117fba0` |
| Kernel config | 39128 | `d35adddd44760a9000cf93f6f51ae7bf68b64d1ddd598e7150b9b408fdc9556c` |

The fresh loader inspection, exact RAM plan and immutable one-peer TFTP receipt
were checked before `bootm`. The device's complete-image CRC32 was `b4b7926c`.
Header/payload addresses remain `0x01ffffc0` / `0x02000000`; physical kernel
BSS ends at `0x005adde8`, below the reserved low 16 MiB. The board profile still
exposes only low 256 MiB, with the first 16 MiB reserved from normal allocation.

Boot evidence: `evidence/ram-sd-ident-tftp-20261013T163853.235489Z.json` / `.rx`.
Received stream SHA-256:
`bdb53c2f172db55ee1483b76206680681ba4116fb8ba058e246b282b53b7c58f`.

## Measured card and controller

| Field | Observation |
|---|---|
| Card type / name | SDHC / `SU04G` |
| Manufacturer | `0x000003` |
| Capacity | 3965190144 bytes, about 3.69 GiB / nominal 4 GB |
| Card clock | 25000000 Hz |
| Bus / timing | `bus_width=0` / `timing=0`: single line / legacy |
| Controller | `0xf9820000`, DW VERID `5342270a`, HCON `00e44c81`, GIC 66 |
| Inherited CRG39 / LDO | `00000203` / `00000060` |
| Host source | 50000000 Hz |
| Interrupt errors | `Err: 0` before and after the diagnostic interval |

Actual card protocol responses establish identification, beyond the earlier
active-low CDETECT observation. The custom non-unique sysfs summary emitted
`SD_IDENT_COMPLETE bytes=3965190144 clock=25000000 bus_width=0 timing=0`.
The RAM-file time64 probe passed with 8-byte `time_t` and epoch `2208988800`.
The board wall clock was not changed.

The inherited-state guard ran before generic DW initialization. Controller
reset/IRQ/FIFO/divider/power writes and native card-identification commands are
part of this experiment; it is not a command-free register audit. Requests
are filtered before the hardware queue: fixed-size SCR/SSR and CMD6 CHECK
metadata are allowed, while CMD6 SET, ACMD6, sectors, writes, erase and unknown
requests are rejected. PIO, single line, legacy and at most 25 MHz are enforced.
MMC/SDIO, high-speed, PM, power-sequence and BLOCK drivers are excluded.
No CRG/LDO provider or voltage switch is used; extension discovery cannot enable
card cache or power settings.

Diagnostic evidence: `evidence/board-sd-ident-20261013T163853.235489Z.json` / `.rx`.
Received stream SHA-256:
`9d4c85268dec163181356f8aba62b9774b7ebdaec267c80b325efca3d35a070c`.
Unique card identifiers, addresses and raw local logs are not published.

## Command restart and restored router

The exact SD DT identity and actual bound restart driver were checked, together
with the measured MV100 SYSID0/zero-ID/inactive-watchdog registration markers.
One explicit restart was sent. The actual shutdown stream included
`SD_IDENT_SHUTDOWN_COMPLETE host-removed clock-disabled no-card-writes` after
DW host removal and read-back checks of IRQ masks, card clock and DMA state.
Boot ROM, DDR initialization and original CA Fastboot then appeared; the same
exclusive UART tool stopped autoboot and completed five fresh read-only loader
queries. There was no automatic reset retry.

An earlier attempt refused before sending restart because minimal BusyBox lacks
`tr`. The corrected CLI reads the binary DT compatibility property with existing
`cat`/`echo`; updated PTY checks pass for actual NUL-separated identity, foreign
DT, missing binding/guard, failed reset and absent/failed shutdown markers.

Restart evidence: `evidence/sd-ident-restart-20261013T164414.415434Z.json` / `.rx`.
Received stream SHA-256:
`0903398fc62620a7872dc5061fb97bdde63c0ff85791289e6ebb7434bfae5ca5`.

The freshly inspected loader accepted both exact router payloads and separate
device CRCs: uImage `3813a6ca`, rootfs `32c0206d`. Their identities match the
[dual-core board report](passwall-dual-core-20261013.md), not the separately built
CI artifacts. Return evidence:
`evidence/ram-dual-core-tftp-20261013T164420.784416Z.json` / `.rx`, stream SHA-256
`9a0971b2a6eb962d961222cf8a99308c8af12b0dd24f3f66c8462239dcea082a`.

Management was re-established, the latest backup's 14 selected configuration,
account and authorized-key files were restored and every hash checked. Root
remains empty; Chinese LuCI and Ethernet are online, IRQ Err is zero. The exact
accepted native restart module was loaded and registered again, so the next
guarded native-router reboot can also be automated. These are RAM changes.
Final restored-router stream SHA-256:
`8034fb021b81479117b33978fa8c9741e13a193a91a851dbca1a97a511cc951a`.
The host received the expected Chinese login challenge, then blank-root login
reached the actual Passwall page with HTTP 200; session credentials are excluded.

## Local validation and remaining work

`make lint`, `make build`, `make test`, `make test-serial` and `make sd-ident`
passed. Actual policy/queue, probe/slot/shutdown, inherited DMA/IRQ takeover and
restart-probe paths pass ASan/UBSan checks. Exact DT/config/resource mutations,
ARM image/CRC/layout and QEMU shell/time64 checks pass. QEMU does not emulate
the physical SD controller.

The current native router still excludes MMC/BLOCK. Sector reads, enforced
read-only block/filesystem integration and hotplug remain separate work. Card
recognition does not establish those behaviors or authorize card writes.
