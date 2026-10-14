# 原生只读 SD 路由系统实测（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The independent `openwrt-router-sdro` RAM candidate passes SD block/VFAT file
reads, higher-memory/PFN stress, physical Ethernet transfers, both Passwall
cores and autonomous command restart. The exact original low-256-MiB Chinese
router and current user configuration were restored after the first trial.
The completed second application trial also returned automatically after the
user reconnected the TTL adapter and actual UART reception recovered. The
original Chinese router is healthy. No card-data,
persistent boot/flash or security-state writes were performed.

## Exact accepted candidate

Official OpenWrt `58efa9917d4cc53fceed173529a286187649e827`, Linux 6.12.112,
native GCC 14.3/musl 1.2.5 and the existing pinned application feeds are reused.
The official branch API again confirmed that commit as the `openwrt-25.12`
head on 2026-10-14 local date. There is no Kwrt customization.

The distinct variant is `ethernet-sdro`, with board identity
`tianyi,ty1208z-ca-openwrt-sdro-ram`, kernel selection `TY1208Z_ROUTER_SD_RO`
and dedicated `router-sd` source/output tree. Ordinary router and diagnostic
profiles retain their separate memory and peripheral gates.

| Payload | Bytes | SHA-256 |
|---|---:|---|
| uImage-UNTESTED.bin | 4133038 | `71dd562b3c3cb57213b541d5fffe08b83a5169de894d1a511deb54543f19eacd` |
| zImage | 4130360 | `3f0176d87805b3ce81f9353e36f3f00b5cf079fe952472df88a1733cd384845e` |
| ty1208z-diagnostic.dtb | 2614 | `3c12b45e469e8a4ce7b8989b1da8c2f0a2d56faa6321c20bea0f5e13c9795b95` |
| linux.config | 70837 | `38d54783f029b932fca51173060132486accc6c7ef94cf20f8ab7869b596f433` |
| rootfs.cpio.gz | 33412270 | `b551da3304314a7062513050c142e255c1fe5e64b8247c8caaefcd7ed1be3f71` |
| packages.manifest | 4669 | `d277544d0d000948011c9877d7f106bf58a793615ce158b6ae45914b844c40b1` |

The compressed initrd remains within the existing 33553919-byte transfer
limit. The exact matched external restart module is bound to the delivered
kernel/config hashes. Fresh preceding command-reboot evidence verifies all
eleven loader allocations; fresh loader inspection, exact low-16-MiB
reservation and low-768-MiB layout, and both independent device CRCs precede
this physical boot. The accepted CA loader and persistent environment remain.

## Storage, memory and network results

The native SD driver binds the measured controller `f9820000`, CRG39/LDO and
SPI34 resources. `SU04G` SDHC reports 3965190144 bytes, two existing partitions,
PIO/one-bit/legacy/25-MHz operation and block read-only state 1. The actual
4096-byte block read and 1024-byte overlap comparison pass. An existing VFAT
file is read through a read-only mount and the mount/directories are removed.
No filenames, contents, serials or credentials are published. The second
partition's filesystem remains unknown; MBR type 83 is not treated as ext4.
Ext4/exFAT mounts, hotplug, writes and storage performance remain unverified.

Read-only protection remains enforced at the DW request queue, beyond the
userspace block flag: writes, erase, CMD6 SET, CMD23, unknown or malformed
requests, range errors and invalid STOP sidecars are denied before hardware
queueing. Ext4 uses `ro,noload`; no repair or journal replay is attempted.

MemTotal is 762296 KiB (744.43 MiB).
Two complete 512-MiB patterns pass; all 131072 pages are present, unswapped and
within the allowed physical range. Observed PFN bounds are
8193..194634; 101746 pages lie above
the ordinary 256-MiB bound. The RAM stress file, tmpfs and directory are removed.
The dedicated native init-memory retention gate preserves low 16 MiB.

Both directions transfer 64 MiB through SSH over the real Ethernet link, with
SHA-256 `281e519df3077b557c6b03f5da83c4e8d397219259615dd7c3308f89cae8f2a6`. The RAM transfer file is removed;
six error/drop/FIFO/carrier counters do not increase. IRQ Err stays zero.
This is data-integrity acceptance, not external routing or throughput measurement.

## Applications and autonomous return

Chinese LuCI with root/empty default login, exact configuration restoration,
strict-CA HTTPS, Passwall-generated Xray and sing-box VLESS/TLS SOCKS, unzip
ZIP64/Chinese/2040-file extraction, local namespace forwarding and TCP/UDP
TPROXY pass on this exact physical kernel. The existing fixture verifies its
configuration hashes and complete cleanup. Board wall time is unchanged;
future-clock/NTP era tests run only inside isolated QEMU.

The first boot of this exact candidate was automatically returned after its
initial SSH connection timed out; runtime SD/memory/application acceptance
belongs to the second boot, not that earlier incomplete test. The second
boot's readiness script initially failed to remove ANSI address coloring;
this was corrected and SSH completed exact configuration/module restoration.
Its UART module-upload fallback then encountered a host RX-zero condition;
SSH recovery loaded only the exact matched module and all runtime tests passed.
Repeated host receivers receive zero even when an SSH-triggered UART marker
advances the board TX counter. A Windows PnP reset returned general failure.
Receive-only COM9 monitors expired without a restart attempt; the latest ended
at 2026-10-14 08:42:59 Asia/Shanghai. After the user reconnected TTL, a fresh
SSH-triggered marker was received in full, with 33 received bytes and matching
board TX progress. Independent SSH identity/IRQ checks preceded interactive
console recovery. No additional manual box power cycle was needed.

The second trial then completed one guarded command restart at 08:59.
Immediately before restart, all 15 current configuration/account/key files
were backed up and independently hash-checked. Actual controller shutdown,
fresh original CA-loader inspection, the exact low256 router's two device
CRCs, current configuration restoration, Chinese authenticated Passwall page,
empty root login, restart binding and IRQ Err0 passed. COM9 was released.
This return is separate from the first trial's accepted return.

In the independently verified first return, the native `router-sdro` guard
verifies its DT/source and matched restart binding. One graceful command
restart emits actual `SD_IDENT_SHUTDOWN_COMPLETE host-removed clock-disabled
no-card-writes`, reaches the original CA loader and performs fresh inspection.
The exact original router's two device CRCs, configuration/account/key hashes,
Chinese authenticated Passwall page, empty root login, restart-module binding
and IRQ Err0 are verified after return. No manual power cycle is required.

## Offline gates and remaining work

Core `make lint/build/test/test-serial` pass. Real Kconfig executes seven
selection/removal cases: native SD, SD disabled, missing RO/MMC/BLOCK/MAC and
ordinary network. The SD option depends on the network base rather than the
Ethernet option, avoiding a dependency cycle; only this independent flag
permits Ethernet with BLOCK/MMC. OpenWrt's default block throttling is disabled
in both selections. Inherited RAM overlayfs is allowed; foreign storage
drivers/filesystems remain rejected.

The actual native SD source, clock/MAC/PHY probes, init retention across all
eight flag combinations, SD policy/probe/DW queue/get_ro and image/resource/
memory mutation gates pass. Exact rootfs/kernel/config/provenance pass both
512-MiB and 240-MiB usable-budget QEMU application suites, including time64,
NTP era crossings, both proxy cores and TCP/UDP TPROXY. QEMU does not emulate
the board's SD controller or prove physical peripherals.

The workflow now includes the separate SD variant and its exact restart module;
clean remote native SD CI remains pending. The restored ordinary router still
uses low 256 MiB and has storage disabled. eMMC blocks/filesystems/backups, actual
ARMv7 Docker containers, RDA firmware/STA/AP and external routing/performance
remain required work. Persistent installation requires its later independent
layout/backup/recovery review and session authorization.
