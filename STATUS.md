# TY1208Z kernel port status

Updated: 2026-10-13. Existing Hinas booted; a read-only SSH baseline was collected.
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
| GitHub CI | Diagnostic CI passed on `fbc1e79`, [run 38304430531](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38304430531), [full report](verification/diagnostic-ci-20261013.md), including shared USB clock/PHY checks, the offline USB host image, deliberate RAM-boot denial and restart candidate. Native core/Ethernet CI passed on `62db42b`, [run 38287462054](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38287462054), including both offline image builds/emulation and hardware-untested uploads. Plain/integrated application CI passed on `62db42b`, [run 38287461985](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38287461985), including both 512/240-MiB QEMU budgets, external-initrd packaging and TCP TPROXY. Downloaded files/provenance/console hashes and markers were verified, [CI report](verification/openwrt-applications-ci-20261013.md). RDA READY rollback also passed that complete diagnostic run; later UDP/NTP fixtures and the new TFTP CLI still await their own complete CI acceptance |
| Existing Hinas SSH baseline | Complete: Ubuntu 24.04.4 armhf/glibc 2.39, original 4.4 kernel, four CPUs, 1 GiB reported RAM and current eMMC layout |
| Serial CLI | Replacing the TTL adapter resolved console input; CLI attached to the stopped CA bootloader on COM9 and completed command/environment queries without another reboot; see [inspection record](verification/bootloader-inspection-20261012.md) |
| Serial stream and optional TFTP | Long RAM-shell file transfer stopped mid-echo; subsequent UART probes received no bytes while board ping remained reachable, [observation](verification/serial-stream-20261013.md). Optional immutable, one-peer TFTP RAM loading now passes independent UDP/curl, full local router snapshots, serial PTY size/CRC/rollback gates and core regression checks, [offline report](verification/tftp-ram-offline-20261013.md). No physical TFTP/throughput or new native OpenWrt acceptance yet |
| Original Hinas TTL boot | Complete from Boot ROM to login; bootloader and allocation evidence recorded in [TTL report](verification/ttl-boot-20261012.md) |
| Candidate boot on physical TY1208Z | Passed for the corrected candidate: Linux 6.12.112, PL011 input/output, initramfs shell, GIC timer interrupts and RAM-file time64; see [physical RAM boot](verification/ram-boot-20261012.md) |
| CA authentication / RAM placement | Current CA bootloader accepted this ordinary unsigned uImage at the measured Hinas address; host/device CRC matched; bounded low-256-MiB diagnostic boot succeeded. This does not establish other loaders/images or persistent installation |
| Hinas startup under new kernel | Not tested; eMMC driver and legacy modules need separate work |
| Wired network / storage / USB / SMP | Not integrated into the plain diagnostic image; [Ethernet source audit](docs/ethernet.md) identifies mainline datapath/MDIO reuse and unresolved MV100 PHY/clock integration |
| eMMC register audit | Passed on hardware: separate RAM candidate, MMC/BLOCK disabled, DW revision `0x270a`, HCON `0x00e44c81`, inherited source 100 MHz; no card commands; [measurement](verification/emmc-audit-20261012.md) |
| eMMC card identification | Passed physically: inherited DMA/IRQ cleanup, CMD1 dual-voltage OCR, `008G30`, EXT_CSD rev 8, 7818182656 bytes; PIO/1-bit/25-MHz legacy mode, BLOCK disabled. Actual policy/core callback/takeover tests and QEMU pass locally. No sector I/O; [hardware report](verification/emmc-identification-20261012.md) |
| eMMC fixed sector reads | Passed physically: exactly four PIO CMD17 user-area reads; Hinas kernel header CRC matches local original, root-partition ext4 magic/block size pass. No block interface, mounts, writes or card-setting changes; [hardware report](verification/emmc-reads-20261012.md) |
| Ethernet inherited-state audit | Passed physically: CRG51 `0x3`, internal PHY clock/reset `0x101`, address 1. MDIO/MAC access skipped because the SDK clock gate requires `0xb`; no PHY ID or working network yet. UART/timer/time64 pass; [hardware report](verification/ethernet-audit-20261012.md) |
| Temporary Ethernet clock / PHY-ID | Passed physically: CRG51 `0x3 -> 0xb -> 0x3`, restoration verified; PHY ID `0x20669823` at address 1 matches FESTAv220. No PHY reset/register, DMA or storage writes. UART/timer/time64 and offline gates pass; [hardware report](verification/ethernet-clock-id-20261012.md) |
| Ethernet inherited-PHY datapath | Passed physically after TX-level/NAPI correction: exact FESTAv220 binding, 100 Mbps full duplex, DHCP/gateway replies, 20/20 DF MTU pings and three software down/up cycles; final RX/TX errors/drops zero. Actual patched datapath functions pass ASan/UBSan. [Hardware report](verification/ethernet-net-20261012.md) distinguishes the booted image from the later fancy-ping [tooling rebuild](verification/ethernet-net-offline-20261012.md). Sustained TCP, cable reconnection and complete cold-start support remain pending |
| Native OpenWrt Ethernet experiment | Separate `net` subtarget built with native compiler/musl and measured board drivers; exact DT/config/image/layout and actual datapath sanitizer checks pass. Actual netifd/rootfs/traffic tools and 2040 iperf3 loopback pass QEMU; plain RAM QEMU and application-config checks also pass after shared tooling changes. [Offline report](verification/openwrt-ethernet-offline-20261012.md); physical startup/network/TCP remain pending |
| USB host0 register audit | Separate RAM candidate built; exact controls/capability resource gates, actual read-only helper ASan/UBSan, profile mutations, image/layout, serial PTY and generic QEMU time64 checks pass locally. Pinned MV100 source resolves the revision branch to SYSID0 without a fuse read. [Offline report](verification/usb-audit-offline-20261012.md); board controls/capabilities and USB host/device operation remain unmeasured |
| USB host0 clock/PHY compile experiment | Optional shared CCF provider and upstream EHCI/OHCI core/platform objects compile as ARM ELF. Actual new helper matches 2048 pinned SDK enable/disable write/delay traces under ASan/UBSan; invalid revision, stuck controls/missing clocks and shutdown-readback failures pass. [Compile report](verification/usb-host-compile-20261013.md). Compile entry produces no boot image; ordinary diagnostic/network/router profiles stay separate. Compile CI passed on 62db42b; board host startup, companion lifetime/enumeration and Wi-Fi remain unverified |
| USB host0 offline enumeration image | Separate `usb-host1` kernel links with exact EHCI/OHCI/shared-clock DTS and no class/storage/network drivers. Actual resource/config mutation gates, deliberate RAM-boot denial, image/layout and QEMU ARM observer/time64 pass locally; [offline report](verification/usb-host-offline-20261013.md). Clean diagnostic CI including this image passed on `3355c5b`; physical control/capability audit, host/device startup and RDA firmware/radio remain pending |
| SP805 system restart | Independent candidate built and checked; real-ID/disabled-control gates, exact reset-helper sanitizer, DT/config/layout, fixed UART restart/inspection PTY and QEMU time64 pass locally. [Offline report](verification/restart-offline-20261012.md). Hardware registration/reset remain untested; the current Ethernet RAM image still requires a physical power cycle |
| Wi-Fi | RDA USB `1e04:8888`; compatible-descriptor source pinned; complete USB module linked locally and in CI against separate Linux 6.12 config, manufacturing eFuse-write entry points excluded, key/WID sanitizer regression passed; [initial module report](verification/wifi-module-port-20261012.md); later control-response fixes and local sanitizer checks in [control report](verification/wifi-control-20261012.md); actual key callbacks now pass cipher/length/role/peer/RSC/MIC and firmware-error sanitizer checks, with AP-reset cache state gated on reply; [key report](verification/wifi-keys-20261013.md). Unimplemented iovar/key operations now return unsupported; existing AP-stop state changes wait for a successful reply, TX-power failures preserve cached/output state and BIP/WAPI capability declarations are removed; actual-function sanitizers and full module link pass locally, [operation report](verification/wifi-operations-20261013.md). Actual USB startup is blocked by missing named-roaming/capability transport; READY now rolls back on initialization failure, with real-function sanitizer and module link pass locally, [startup report](verification/wifi-startup-20261013.md). Chip revision, firmware and hardware operation remain unverified |
| OpenWrt/Kwrt / Passwall | [Independent native RAM target](docs/openwrt.md) built with GCC 14.3/musl 1.2.5 and passed core time64 QEMU/CI. Separate pinned [application target](docs/openwrt-applications.md) now builds real Passwall/Xray/LuCI and passes ARM QEMU at 2040 for DNS/TLS, authenticated Passwall UI, real SOCKS data flow and nft counters/socket/TPROXY expressions; [result](verification/openwrt-applications-20261012.md). Plain/integrated native application/TCP CI passed on `62db42b`; physical OpenWrt, hardware routing/TPROXY/performance, Wi-Fi and Kwrt customization remain pending |
| Application external-initrd RAM packaging | Exact native application kernel/rootfs also passes full QEMU acceptance with a 240-MiB usable cap; separate checked uImage/DTB and bounded initrd at `0x04000000` are packaged. Actual profile/provenance mutations, two-CRC serial PTY, ordinary CRC/DDR regressions and guarded plan against recorded loader responses pass locally. [Offline report](verification/openwrt-apps-ram-offline-20261013.md); wrapper CI passed on `62db42b`; physical transfer/boot remains untested. This profile has no board Ethernet/storage/USB/SMP |
| Applications/Ethernet RAM integration | Separate native router variant builds Passwall/Xray/LuCI, matching modules and measured Ethernet drivers. Real netifd/fw4 forwarding, Passwall TCP TPROXY HTTPS and bidirectional UDP pass isolated ARM QEMU at 2040 with 512/240-MiB budgets; direct traffic fails before/after proxy service, actual counters/policy routing pass. Wrapper/resource/provenance/CRC/UART checks and actual built FEMAC sanitizer pass locally. [Report](verification/openwrt-router-offline-20261013.md); installed one-shot NTP crosses 2036/2038 and sets 2040 in both QEMU budgets; integrated build/TCP/packaging CI passed on `62db42b`; later UDP/NTP CI, physical boot/routing/proxy/performance and physical NTP remain unverified. Storage/USB/Wi-Fi/SMP excluded |
| Pinned source download recovery | Diagnostic CI on `57a77c7` failed before compilation because the BusyBox HTTPS connection was refused. Bounded retry, SHA-preserving temporary publication, nine regression tests and a real fresh local download pass; [report](verification/source-download-20261013.md). The later complete `7bad089` [diagnostic run 38300887226](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38300887226) passed fresh download/build, all diagnostic profiles, Wi-Fi operation guards and uploads; the later READY rollback also passed the complete `fbc1e79` run 38304430531 |
| NTP protocol/time64 | Installed BusyBox client corrects all four fixed loopback cases across 2036/2038 and from 2026 to 2040; plain/integrated images pass both 512/240-MiB QEMU budgets. Required RAM-provenance marker and fixture-exclusion checks pass. [Report](verification/openwrt-ntp-time64-20261013.md); normal physical NTP service/clock remains unverified |
| Whole-system Y2038 | Not established; core, selected applications and one-shot NTP emulation passed. Persistent filesystems, other protocols and physical whole-system behavior remain unverified |

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
then verified timer/uptime progress and the time64 probe. Restricted eMMC
reads and basic wired Ethernet now have separate physical acceptance. The
next work is native OpenWrt Ethernet integration and sustained traffic, USB/
Wi-Fi, broader storage support and Hinas compatibility.

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
