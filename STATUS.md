# TY1208Z kernel port status

Updated: 2026-10-12. Existing Hinas booted; a read-only SSH baseline was collected.
No flashing, persistent boot changes or OTP writes were performed by this project. Offline
implementation and repository push are authorized.

Target: modern Linux, native OpenWrt/Kwrt, Passwall, board Wi-Fi and verified
time64 behavior. The current milestone is a RAM-only, single-core diagnostic.

| Stage | Result |
|---|---|
| Original firmware/source audit | Completed offline; file identities, DTB and pinned SDK references recorded |
| Exact Hinas 4.4 source rebuild | Not performed; exact ecoo source unavailable; vendor reference is not equivalent |
| Linux 6.12.112 candidate | Cross-compiled; board descriptor, UART/GIC DTB, single-core timer and embedded initramfs |
| Structural checks | Passed: CRC, ARM uImage/zImage, appended DTB, static ARM ELF, required/disabled config |
| QEMU virt | Passed: same raw zImage + initramfs; shell, 2040 clock read/write, RAM file times and BusyBox stat |
| GitHub CI | Diagnostic CI passed on `af89935`, including fixed eMMC reads, [run 38240961797](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38240961797); native OpenWrt CI passed on `99bdd88`, [run 38230366184](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38230366184). Newer native/application CI results are tracked separately |
| Existing Hinas SSH baseline | Complete: Ubuntu 24.04.4 armhf/glibc 2.39, original 4.4 kernel, four CPUs, 1 GiB reported RAM and current eMMC layout |
| Serial CLI | Replacing the TTL adapter resolved console input; CLI attached to the stopped CA bootloader on COM9 and completed command/environment queries without another reboot; see [inspection record](verification/bootloader-inspection-20261012.md) |
| Original Hinas TTL boot | Complete from Boot ROM to login; bootloader and allocation evidence recorded in [TTL report](verification/ttl-boot-20261012.md) |
| Candidate boot on physical TY1208Z | Passed for the corrected candidate: Linux 6.12.112, PL011 input/output, initramfs shell, GIC timer interrupts and RAM-file time64; see [physical RAM boot](verification/ram-boot-20261012.md) |
| CA authentication / RAM placement | Current CA bootloader accepted this ordinary unsigned uImage at the measured Hinas address; host/device CRC matched; bounded low-256-MiB diagnostic boot succeeded. This does not establish other loaders/images or persistent installation |
| Hinas startup under new kernel | Not tested; eMMC driver and legacy modules need separate work |
| Wired network / storage / USB / SMP | Not integrated into the plain diagnostic image; [Ethernet source audit](docs/ethernet.md) identifies mainline datapath/MDIO reuse and unresolved MV100 PHY/clock integration |
| eMMC register audit | Passed on hardware: separate RAM candidate, MMC/BLOCK disabled, DW revision `0x270a`, HCON `0x00e44c81`, inherited source 100 MHz; no card commands; [measurement](verification/emmc-audit-20261012.md) |
| eMMC card identification | Passed physically: inherited DMA/IRQ cleanup, CMD1 dual-voltage OCR, `008G30`, EXT_CSD rev 8, 7818182656 bytes; PIO/1-bit/25-MHz legacy mode, BLOCK disabled. Actual policy/core callback/takeover tests and QEMU pass locally. No sector I/O; [hardware report](verification/emmc-identification-20261012.md) |
| eMMC fixed sector reads | Passed physically: exactly four PIO CMD17 user-area reads; Hinas kernel header CRC matches local original, root-partition ext4 magic/block size pass. No block interface, mounts, writes or card-setting changes; [hardware report](verification/emmc-reads-20261012.md) |
| Ethernet inherited-state audit | Passed physically: CRG51 `0x3`, internal PHY clock/reset `0x101`, address 1. MDIO/MAC access skipped because the SDK clock gate requires `0xb`; no PHY ID or working network yet. UART/timer/time64 pass; [hardware report](verification/ethernet-audit-20261012.md) |
| Temporary Ethernet clock / PHY-ID candidate | Built separately; exact measured-state guards, volatile bit-3 enable, bounded ID reads and clock restoration tested under sanitizers. DT/config/image/QEMU/serial gates pass. Physical PHY-ID/restoration acceptance pending; [scope](docs/ethernet.md) |
| Wi-Fi | RDA USB `1e04:8888`; compatible-descriptor source pinned; complete USB module linked locally and in CI against separate Linux 6.12 config, manufacturing eFuse-write entry points excluded, key/WID sanitizer regression passed; [initial module report](verification/wifi-module-port-20261012.md); later control-response fixes and local sanitizer checks in [control report](verification/wifi-control-20261012.md); chip revision, firmware and hardware operation remain unverified |
| OpenWrt/Kwrt / Passwall | [Independent native RAM target](docs/openwrt.md) built with GCC 14.3/musl 1.2.5 and passed core time64 QEMU/CI. Separate pinned [application target](docs/openwrt-applications.md) now builds real Passwall/Xray/LuCI and passes ARM QEMU at 2040 for DNS/TLS, authenticated Passwall UI, real SOCKS data flow and nft counters/socket/TPROXY expressions; [result](verification/openwrt-applications-20261012.md). Application CI, physical OpenWrt, hardware routing/TPROXY/performance, Wi-Fi and Kwrt customization remain pending |
| Whole-system Y2038 | Not established; core and selected application emulation passed. NTP, persistent filesystems, other protocols and physical whole-system behavior remain unverified |

Known-successful CA bootloader SHA-256:
`f891870ec98b4df48de879afc1e1973cf14cc9057eb18a5a41d974fab3e935bc`.

The candidate is an ordinary unsigned uImage, not ADVCA packaged or ready to
flash. Header/load/entry follows the measured original Hinas RAM boot path.
Diagnostic memory is restricted to the low 256 MiB of measured 1 GiB DDR; the
low 16 MiB is reserved from allocation according to the live ddrfree lower
bound. This is not a complete secure-memory or OTP map.

Live bootloader help confirms bootm, TFTP, Kermit, YMODEM and CRC32. The current
environment confirms bootdelay=0 and the existing header at 0x01ffffc0. ddrfree
reports 0x01000000..0x40000000; this broad range includes observed high boot
allocations, so it is not treated as an allocator map. The bounded candidate
reuses the original load address, stays below all observed high allocations,
and has a verified decompression footprint ending below 16 MiB. The first boot
reached /init but lacked a console because of an incorrect UART periphid
override. Removing the override made PL011 bind; serial diagnostic capture
then verified timer/uptime progress and the time64 probe. The next board work
is storage and wired-network support with separate validation, followed by
Hinas compatibility and the OpenWrt/Kwrt target.

The actual CI result above covers the RAM boot tooling, corrected diagnostic
DTB, independent RDA USB audit and separate eMMC register audit. It reproduces the software checks; physical
acceptance and shell observations are recorded separately for the local image.

The first Windows collection reached its END marker but exited 127 because
PowerShell appended CRLF to the script. The collector now exits explicitly and
passes local LF/CRLF transport regression. The saved hardware report is usable;
raw logs and runtime FDT stay in ignored local evidence. Anonymized measurements
are in [verification/baseline-20261012.md](verification/baseline-20261012.md).

See `docs/hardware.md`, `docs/wifi.md` and `docs/validation.md` for evidence and
limits. No flash commands are provided at this stage.

Serial collection now uses [the CLI workflow](docs/ttl-baseline.md), without
HiTool for routine UART access. Local validation is recorded in
[verification/serial-cli-20261012.md](verification/serial-cli-20261012.md).
