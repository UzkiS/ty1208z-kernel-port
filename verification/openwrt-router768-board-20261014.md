# 低768原生路由内存与应用实测（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The independent router768 variant passed physical RAM, Ethernet/application
and command-restart acceptance on TY1208Z CA / Hi3798MV100 on 2026-10-14.
The ordinary router remains on its original low-256-MiB profile; this new
variant has its own kernel, board identity, build directory and matched
restart module. No flash, persistent boot, SD/eMMC or security-state writes
were performed. COM9 was released after automatic return to the original
Chinese OpenWrt and current configuration.

## Exact build and RAM gates

Official OpenWrt remains pinned to 58efa991, Linux 6.12.112, native
GCC 14.3/musl 1.2.5, Passwall 26.10.4 and the same locked Xray/sing-box/unzip
recipes. The external rootfs and its matching kernel/modules passed isolated
512/240-MiB application budgets, including 2040 NTP/time64, DNS/TLS,
Chinese/empty-root LuCI, both SOCKS/TLS cores and TCP/UDP TPROXY.
The future wall-clock tests were confined to QEMU.

The DT exposes only low 768 MiB, reserves low 16 MiB and excludes the upper
256 MiB. Its exact opt-in configuration retains ARM init pages and permits
the new identity in the existing resource-checked Ethernet and restart
module probes. BLOCK/MMC/MTD/USB/SMP/highmem/watchdog-device support remains
disabled. A real initial build exposed OpenWrt's upper-layer disabling of
PROC_PAGE_MONITOR; the independent native configuration now selects it at
both OpenWrt and Linux layers. The final actual kernel contains it.

Before transfer, a guarded command reboot provided the complete, hash-checked
eleven-allocation table and fresh CA/1-GiB loader inspection. Both the kernel
and initrd were checked with independent device CRCs. Layout, low reservation,
freshness/port/table identity, exact DT/config/provenance and two-payload CRC
gates passed. Missing and stale allocation evidence were rejected by actual
artifact tests and serial PTYs.

| File | Bytes | SHA-256 |
|---|---:|---|
| uImage-UNTESTED.bin | 3445388 | 83098575ef12bcad71375d0166a366c08dd76006641130789408a1d974ec10a1 |
| zImage | 3443016 | 7f24b9dd0e15727d3945b3bf9fe25ddae740ac0a49ace97301df1f483edf6627 |
| ty1208z-diagnostic.dtb | 2308 | e89a2f3b2e86090dccbd3dcf652990f549e6f0b9380687f63be2b321d465137b |
| linux.config | 64550 | 7ce18b5ee7f8158e7da17e14c09f6090ece32b2f4169ede37b74554061eb3c26 |
| rootfs.cpio.gz | 33408607 | 74fb9b71f1bc5bfccccb3db54515ec79aa8a22d842367f4b8c5d4ec985202ccc |
| packages.manifest | 4669 | dd811a897b975e2f7334516f119abdcb25180e22d8176b27c40a86a680eb1338 |
| matched restart module | 124304 | 60ca1db6232e373876f25ca4f58e306a25f8ee7983b87b8f89b85ab520ef4f39 |

Kernel device CRC: 29b11c19; initrd device CRC:
580fafb1. Physical BSS ends at
0x009c0b80, below 16 MiB.
Fresh loader allocation stream SHA-256:
0e3332dbea2ac51b3df68434f6e5e2a9d726d23f6c168304ce7f8be1aa01ee2a.

## Physical memory and Ethernet

MemTotal was 762296 KiB (about 744.43 MiB).
The exact already accepted static ARM probe wrote/read two complete
512-MiB address-dependent/complement patterns in a dedicated RAM tmpfs.
All 131072 pages were present, unswapped and within the allowed physical
range. Minimum/maximum PFNs were 8237 / 194665;
99645 pages (about 389.24 MiB) lay above 256 MiB.
The test file, mount and directory were removed. IRQ Err remained zero;
RAM-file time64 passed. Board wall time was not changed.

The measured FESTAv220/100-Mbps-full-duplex Ethernet returned with DHCP,
gateway/DNS/NTP. SSH over the physical Ethernet transferred 64 MiB in
each direction with identical SHA-256
281e519df3077b557c6b03f5da83c4e8d397219259615dd7c3308f89cae8f2a6.
The six RX/TX error/drop/FIFO/carrier counters did not increase, and the
RAM transfer file was removed. This verifies transport/data integrity;
it is not a maximum-throughput or external-routing measurement.

Memory evidence stream SHA-256: 28b25a2bae667387fa90239ffec461a5d886b90030c0e1bd810db8bf041ad2d8.

## Applications, restart and restoration

The actual ARM/SoC fixture passed ZIP64/Chinese/2040-file unzip, strict-CA
HTTPS, Passwall-generated Xray and sing-box VLESS/TLS SOCKS, namespace
forwarding and bidirectional TCP/UDP TPROXY. All nine expected markers
were present, existing network/firewall/Passwall configuration hashes were
preserved and fixture cleanup completed. Endpoints were local namespaces;
this is not external Ethernet routing or sing-box TPROXY acceptance.
Application stream SHA-256: 797b9a6e61bfd6f81b12d185549c87cdf471f3a07bedbf3e7b913dbd6c2e7cd8.

The matched native restart module registered only after exact module/kernel
and DT identity checks. Graceful command reboot reached the original CA
loader without a manual power cycle. A fresh inspection gated the exact
original router's kernel/rootfs transfer and two device CRCs. Current
configuration/account/key restoration verified all 14 selected hashes,
then Chinese blank-root LuCI/Passwall returned HTTP 200, IRQ Err was zero
and the original restart module was registered again.

Returned configuration archive SHA-256: f3bf9b4e62dcb5c8974e10646a8d7c5ddb271c12c32154cbe83b863bab081095.
Return health stream SHA-256: 83bfb3ef9cd2747bf47cabcafa2806b314407d22629a303e1b6da5f0120ecc58.
Higher-memory command-restart stream SHA-256: 4e20bf85ee4d1573c5b009bc89668452454c2c9562f452e7d4a76980c2ab8cf6.

Local lint/core build/time64, serial PTYs, actual init/clock/MAC/PHY/module
sanitizers, both application budgets and exact packaging/mutation checks
passed. Six actual native configurations had no new unanswered options.
The older plain/router artifacts also passed their updated profile/CRC PTYs.
Clean CI for this newer native integration remains pending. The downloaded
f48 diagnostic run is independently verified in
[the diagnostic report](ram768-ci-20261014.md); it predates router768.

SD/eMMC integration, real Docker daemon/container/resource/network
acceptance, RDA firmware/STA/AP, external routing/performance and a separately
authorized persistent installation remain outstanding.
