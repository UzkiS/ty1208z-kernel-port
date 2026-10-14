# TY1208Z kernel port status

Updated: 2026-10-15. Compact official Chinese LuCI first installation is
physically complete: full 1-GiB p9 and p6 readback, real eMMC ext4 rw root boot,
and online growth to all 6846 MiB pass. Cold boot preserves configuration and
Docker container content; Docker 29.6.1 starts automatically and Chinese
Dockerman displays the live engine. Its disk-root snapshotter is overlayfs.

The earlier 131287242-byte native sysupgrade image adds block-mount/lsblk, built-in
USB mass storage and a fix for disk-root shutdown hanging in del_gendisk.
The exact image physically passes official Chinese LuCI upload/hash/keep-config
confirmation, stage2 RAM pivot, default eMMC reboot, unchanged configuration,
Docker data/autostart and the Chinese mount page. One ordinary disk-root reboot
passes the repaired host-retained MMC shutdown, fresh eleven-allocation table
and default eMMC boot without UART input. See the
[physical upgrade report](verification/native-web-upgrade-board-20261015.md).

The latest 131399882-byte image adds built-in NTFS3 and passes another official
keep-configuration LuCI upgrade/default boot. A 320a:827b USB2 disk (58.2 GiB)
passes VFAT and NTFS3 read-only file reads/unmount; NTFS access leaves USB write
counters unchanged. See the [USB report](verification/usb-storage-board-20261015.md).
SD remains request-level read-only. Wi-Fi STA and AP pass; Wi-Fi-uplink
bypass-routing is not measured. Fresh-build CI closure remains pending;
see the [CI repair record](verification/ci-closure-20261015.md).
The existing CA fastboot, persistent boot environment, other eMMC partitions and
boot0/boot1/RPMB are preserved. Private firmware/backups/UART are not published.
See [current progress](verification/progress-20261014.md),
[first installation](verification/compact-first-install-board-20261014.md) and
[installation/upgrade instructions](docs/installation-plan.md).

## Historical development evidence

The following records describe their dated independent profiles; pending
statements in those historical entries are not the current integrated status.

Target: modern Linux, official native OpenWrt, Passwall, board Wi-Fi and verified
time64 behavior. The current milestone is single-core RAM-only native network/
application acceptance, with USB and Wi-Fi validated separately.

The integrated native RAM system now physically runs Docker on the board with
762296 KiB usable RAM and both read-only SD/eMMC hosts. A small ARMv7 container
passes overlay2, memory/CPU quota readback, default seccomp, gateway DNS and
TCP/HTTP through physical Ethernet. Flat OpenWrt module layout and correct
Docker/uplink firewall zones fix the initial integration failures. Both hosts
shut down before command restart, and the original Chinese router/configuration
was restored automatically. The normal source/build/package entry is
`make openwrt-system`; [physical report](verification/openwrt-system-board-20261014.md).
The final repackaged delivery is not a fresh whole-artifact boot trial: unchanged
kernel/application evidence is reused, and changed module, wireless management,
APK and UI boundaries were checked separately. APK integration and STA/AP now
pass; writable persistent storage and installation remain unfinished. Historical
profiles and their earlier boundaries below are retained.

User preferences: future LuCI builds default to Simplified Chinese, onboard
Wi-Fi acceptance includes AP, and required [Docker support](docs/containers.md)
follows verified higher-memory and storage support. The board has 1 GiB
physical DDR; the integrated system exposes measured low 768 MiB (about 744 MiB
usable). The ordinary recovery router still exposes only low 256 MiB.
User requested an empty default root password on 2026-10-13; the built plain
and router rootfs already use it. RAM setup must stop adding random passwords;
only explicitly user-configured passwords are preserved on later restoration.
The separate low-768-MiB memory profile now passes physical 512-MiB stress,
all-page PFN bounds and automatic return/configuration restoration, with about
745.18 MiB usable RAM; [memory report](verification/ram768-board-20261014.md).
Its dedicated init area remains reserved. An independent native router768
variant now physically passes 512-MiB/PFN stress with about 744.43 MiB usable,
64 MiB of verified TCP data in each direction, both proxy cores and automatic
return/configuration restoration; [native report](verification/openwrt-router768-board-20261014.md).
The restored ordinary router still uses low 256 MiB. Storage/production
integration and physical Docker remain pending.
The independent native read-only SD router now physically passes SD block/
VFAT reads, 512-MiB/PFN stress, both physical TCP directions and both proxy
cores. Both exact-image trials completed command restart and original
router/configuration return. After the user reconnected the TTL adapter,
actual COM9 reception and interactive input recovered; the second runtime
trial returned automatically with fresh configuration backup and both
device CRCs verified. No card/persistent writes occurred;
[native SD report](verification/openwrt-sdro-board-20261014.md).
Clean remote native SD CI, eMMC backups and physical Docker remain pending.
The eMMC user-area read-only groundwork passes actual request/queue/slot and
both block-core suppression paths under ASan/UBSan, selected Kconfig and ARM
objects; [object report](verification/emmc-ro-offline-20261014.md).
The separate low256 `emmc-ro1` RAM candidate now also builds with measured
partitions, ext4 ro,noload, controller shutdown and guarded restart. Actual
functions, ARM guest-shell, layout/CRC, PTY and QEMU checks pass. The corrected
MMC disk-flag candidate now physically passes nine-partition/RO checks,
block/overlap/end/header reads, ext4 ro,noload file read/unmount, measured
shutdown and command restart with exact original-router/config return.
New actual MMC readonly/force_ro regressions reproduce the old failure and
pass both corrected profile states. Full backups, native integration and
physical Docker remain pending; [board report](verification/emmc-ro-board-20261014.md).
The latest receive-only monitor expired at 08:42:59 Asia/Shanghai without a
restart attempt. The subsequent user TTL reconnection restored actual UART
reception. One guarded command restart at 08:59 verified SD controller shutdown,
fresh CA-loader inspection, exact original-router transfers/device CRCs and
current configuration restoration. Chinese authenticated LuCI, empty root
login, restart binding and IRQ Err0 pass after return. COM9 is released;
no manual box power cycle was needed.
Actual native Docker now passes an isolated ARMv7 QEMU runtime suite: overlay2,
default seccomp, cgroup CPU/memory enforcement, container lifecycle, bridge
DNS/HTTP, guest-only masquerade/DNAT and daemon shutdown. The dependency profile
now supplies the missing nft NAT modules. These large QEMU-only outputs remain
separate from board images; physical Docker and fresh
runtime CI remain pending; [runtime report](verification/container-qemu-runtime-20261014.md).
The independent combined native application/Docker profile now passes actual
procd/overlay2/cgroups/seccomp/tini, netifd/fw4/DNS/NAT/published ports, both
installed Passwall cores from an actual container network namespace and clean
shutdown alongside Chinese/empty-password/unzip/time64 checks. The canonical
build/test/export command passes all 26 required markers; 17 combined and 13
native core delivery files were independently verified and copied. This uses
the recorded E848 patch and remains QEMU-only, without a board image or physical
Docker/storage/Wi-Fi acceptance. Fresh combined CI is pending;
[combined report](verification/container-applications-qemu-20261014.md).
Downloaded clean diagnostic
CI on f48bb5e passed 16 manifests/162 files and 15 uImage CRCs, including
actual memory/SD/ARM-mount checks; [CI report](verification/ram768-ci-20261014.md).
The new native memory integration has not yet completed clean remote CI.
The newer diagnostic run on `76009fb` also passes: 18 downloaded manifests,
178 declared files and 16 uImage CRCs were independently verified, including
actual eMMC RO object/guest/probe/shutdown/reset/profile checks and exact
committed source identities; [eMMC CI report](verification/emmc-ro-ci-20261014.md).
The later `bca9065` diagnostic artifact independently passes the same counts
and committed-source checks, plus both actual MMC readonly/force_ro profile
states and the ARM buffered-UART-report regression. Native eMMC OpenWrt now
physically passes RAM boot, read-only block/ext4 file reads and Ethernet.
A full private 7818182656-byte user-area backup passes exact length, successful
SSH exit and host readback SHA-256. Native controller shutdown, one guarded
command restart and exact Chinese-router/configuration return also pass;
[native eMMC report](verification/openwrt-emmcro-board-20261014.md).
The user removed Kwrt customization and requires both Xray and sing-box in
Passwall, plus unzip. Both cores and InfoZIP now build in the plain/router
variants and pass both QEMU budgets, including actual Passwall SOCKS/TLS,
Chinese/empty-password login and ZIP extraction; [dual-core report](verification/passwall-dual-core-20261013.md).
The plain image remains hardware untested; the final router now passes physical
dual-core/unzip acceptance and [autonomous command restart](verification/native-restart-board-20261013.md).
The separate SD identification RAM profile now identifies a nominal 4-GB
SDHC card and passes command restart, verified controller shutdown and
automatic return to Chinese OpenWrt; [SD board report](verification/sd-ident-board-20261013.md).
The separate enforced read-only SD profile now also passes block/page/overlap
reads, two-partition discovery, an actual VFAT mount/file-read/unmount and
automatic return; [read-only report](verification/sd-ro-board-20261013.md).
The second partition's filesystem, hotplug and native-router integration
remain pending; see [SD/TF](docs/sd.md).
On 2026-10-13 live GitHub branch/compare checks, repeated on 2026-10-14, confirmed
the pinned `58efa991` still equals the latest `openwrt-25.12` head; master is
a separate, newer development branch. Additional package/runtime work remains.

| Stage | Result |
|---|---|
| Original firmware/source audit | Completed offline; file identities, DTB and pinned SDK references recorded |
| Exact Hinas 4.4 source rebuild | Not performed; exact ecoo source unavailable; vendor reference is not equivalent |
| Linux 6.12.112 candidate | Cross-compiled; board descriptor, UART/GIC DTB, single-core timer and embedded initramfs |
| Structural checks | Passed: CRC, ARM uImage/zImage, appended DTB, static ARM ELF, required/disabled config |
| QEMU virt | Passed: same raw zImage + initramfs; shell, 2040 clock read/write, RAM file times and BusyBox stat |
| GitHub CI | Diagnostic CI passed on `9e5bd2b`, [run 38310319501](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38310319501), [full report](verification/diagnostic-ci-20261013.md), including real UDP/curl TFTP and UART PTY rollback gates, all independent profiles, USB clock/PHY checks, deliberate USB-host RAM-boot denial, RDA READY rollback and directed-scan dispatch/logging. Downloaded Wi-Fi manifest files and actual scan/startup/control sanitizer markers were verified. Later scan-result parser CI also passed on `e52cfb5`, [run 38313816693](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38313816693); six actual Wi-Fi manifest files and all six sanitizer markers were verified. Native core/Ethernet CI passed on `62db42b`, [run 38287462054](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38287462054). Plain/integrated application CI passed on `62db42b`, [run 38287461985](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38287461985), including both 512/240-MiB QEMU budgets, external-initrd packaging and TCP TPROXY; downloaded files/provenance/console hashes and markers were verified, [CI report](verification/openwrt-applications-ci-20261013.md). Later UDP/NTP application CI also passed on `c25f83d`, [run 38298432025](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38298432025); all four actual artifacts, console hashes, source identities, era cases and bidirectional UDP counters were independently verified |
| Existing Hinas SSH baseline | Complete: Ubuntu 24.04.4 armhf/glibc 2.39, original 4.4 kernel, four CPUs, 1 GiB reported RAM and current eMMC layout |
| Serial CLI | Replacing the TTL adapter resolved console input; CLI attached to the stopped CA bootloader on COM9 and completed command/environment queries without another reboot; see [inspection record](verification/bootloader-inspection-20261012.md) |
| Serial stream and optional TFTP | Immutable one-peer TFTP passes UDP/curl, full router snapshots and UART size/CRC/rollback gates. Exact corrected TX and later Chinese kernel/initrd completed fresh physical TFTP receipts/filesizes/device CRCs and original-loader-network restoration. Windows pyserial RX-zero recurred; a bounded .NET SerialPort bridge received fastboot and completed inspection/TFTP/boot/native shell. The user identified a dropped serial 3.3-V supply during later garbled attempts; restored supply allowed successful Chinese boot. Earlier pyserial RX-zero cause remains separate. COM9 is released; [board report](verification/openwrt-router-board-20261013.md) |
| Original Hinas TTL boot | Complete from Boot ROM to login; bootloader and allocation evidence recorded in [TTL report](verification/ttl-boot-20261012.md) |
| Candidate boot on physical TY1208Z | Passed for the corrected candidate: Linux 6.12.112, PL011 input/output, initramfs shell, GIC timer interrupts and RAM-file time64; see [physical RAM boot](verification/ram-boot-20261012.md) |
| CA authentication / RAM placement | Current CA bootloader accepted this ordinary unsigned uImage at the measured Hinas address; host/device CRC matched; bounded low-256-MiB diagnostic boot succeeded. This does not establish other loaders/images or persistent installation |
| Hinas startup under new kernel | Not tested; eMMC driver and legacy modules need separate work |
| Wired network / storage / USB / SMP | Not integrated into the plain diagnostic image; [Ethernet source audit](docs/ethernet.md) identifies mainline datapath/MDIO reuse and unresolved MV100 PHY/clock integration |
| eMMC register audit | Passed on hardware: separate RAM candidate, MMC/BLOCK disabled, DW revision `0x270a`, HCON `0x00e44c81`, inherited source 100 MHz; no card commands; [measurement](verification/emmc-audit-20261012.md) |
| eMMC card identification | Passed physically: inherited DMA/IRQ cleanup, CMD1 dual-voltage OCR, `008G30`, EXT_CSD rev 8, 7818182656 bytes; PIO/1-bit/25-MHz legacy mode, BLOCK disabled. Actual policy/core callback/takeover tests and QEMU pass locally. No sector I/O; [hardware report](verification/emmc-identification-20261012.md) |
| eMMC fixed sector reads | Passed physically: exactly four PIO CMD17 user-area reads; Hinas kernel header CRC matches local original, root-partition ext4 magic/block size pass. No block interface, mounts, writes or card-setting changes; [hardware report](verification/emmc-reads-20261012.md) |
| eMMC user-area read-only blocks | Corrected independent low256 candidate physically passes RO=1 and all nine partitions, block/overlap/end/header/ext4 checks, ext4 ro,noload mount/444-byte existing-file read/unmount, measured controller shutdown and command restart with exact original Chinese router/configuration return. The actual MMC readonly/force_ro regression reproduces the old disk-flag failure and passes both corrected profile states. Native integration, full backups, writes and physical Docker remain pending; [board report](verification/emmc-ro-board-20261014.md) |
| Ethernet inherited-state audit | Passed physically: CRG51 `0x3`, internal PHY clock/reset `0x101`, address 1. MDIO/MAC access skipped because the SDK clock gate requires `0xb`; no PHY ID or working network yet. UART/timer/time64 pass; [hardware report](verification/ethernet-audit-20261012.md) |
| Temporary Ethernet clock / PHY-ID | Passed physically: CRG51 `0x3 -> 0xb -> 0x3`, restoration verified; PHY ID `0x20669823` at address 1 matches FESTAv220. No PHY reset/register, DMA or storage writes. UART/timer/time64 and offline gates pass; [hardware report](verification/ethernet-clock-id-20261012.md) |
| Ethernet inherited-PHY datapath | Passed physically after TX-level/NAPI correction: exact FESTAv220 binding, 100 Mbps full duplex, DHCP/gateway replies, 20/20 DF MTU pings and three software down/up cycles; final RX/TX errors/drops zero. Actual patched datapath functions pass ASan/UBSan. [Hardware report](verification/ethernet-net-20261012.md) distinguishes the booted image from the later fancy-ping [tooling rebuild](verification/ethernet-net-offline-20261012.md). Sustained TCP, cable reconnection and complete cold-start support remain pending |
| Native OpenWrt Ethernet experiment | Separate `net` image passed physical RAM boot, exact native/rootfs/DT identity, FESTAv220 100-Mbps full-duplex binding, DHCP/gateway and RAM-file time64. Bidirectional TCP and a physical cable down/up with DHCP/gateway recovery completed. Board uptime matches Windows under idle/load; independently measured WSL clock drift explains differing iperf durations. The booted full-queue `NETDEV_TX_BUSY` branches incorrectly increase drop/FIFO counters; the later [TX source correction](verification/femac-xmit-20261013.md) passes actual-function ownership/retry tests and fresh local builds, and the corrected router image now passes physical bidirectional TCP with zero additional error/drop/FIFO counts; initial cumulative TX drop remains 3. [Physical report](verification/openwrt-ethernet-board-20261013.md) and [offline report](verification/openwrt-ethernet-offline-20261012.md); complete PHY cold start and router/Wi-Fi remain separate |
| FEMAC TX backpressure | Both BUSY paths preserve skb ownership and drop/FIFO statistics; real DMA failure retains one free/drop. Old actual native source fails the new regression; corrected shared/native source passes 13,312 actual TX calls under ASan/UBSan. Local core/Ethernet/native-router builds and both QEMU budgets pass. The exact corrected router image now boots physically and completes both TCP directions with zero additional error/drop/FIFO/carrier counts; cumulative TX drop remains the initial 3, cause unknown. Fresh diagnostic CI [38354999973](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38354999973) passes on `b9b1fe3`; 11 downloaded manifests/109 files, ten uImage CRC/structure checks and actual TX/datapath markers were independently verified. [TX report](verification/femac-xmit-20261013.md). Native/application TX CI and external routing performance remain pending |
| USB host0 register audit | Physical RAM audit passed: SYSID0 `0x37980100`, CRG46 `0x0013707f`, CRG47 `0x00000b01`, USB0 `0x000c71a8`, USB1 zero. Controller/PHY resets remain asserted, so capability reads were correctly skipped. UART/timer/RAM-file time64 and complete read-only markers passed. [Physical report](verification/usb-audit-board-20261013.md), [offline report](verification/usb-audit-offline-20261012.md); a bounded clock/PHY capability experiment is still required before USB-host boot permission; no fuse read, control write or USB transaction |
| USB host0 clock/PHY compile experiment | Optional shared CCF provider and upstream EHCI/OHCI core/platform objects compile as ARM ELF. Actual new helper matches 2048 pinned SDK enable/disable write/delay traces under ASan/UBSan; invalid revision, stuck controls/missing clocks and shutdown-readback failures pass. [Compile report](verification/usb-host-compile-20261013.md). Compile entry produces no boot image; ordinary diagnostic/network/router profiles stay separate. Compile CI passed on 62db42b; board host startup, companion lifetime/enumeration and Wi-Fi remain unverified |
| USB host0 guarded capability experiment | Independent `usb-clock-audit1` requires the exact five physically measured inactive controls before fixed volatile clock/PHY initialization, four capability reads and verified SDK last-user stop. Actual helper/probe sanitizers, missing-resource/error paths, exact compiled profile, common RAM plan, core build/time64 and candidate QEMU pass. Diagnostic CI [38364481882](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38364481882) passed on `f7e9a61`; twelve actual manifests/119 files, eleven uImage checks, new USB log markers and the downloaded exact USB profile were independently verified. Analog tuning is not restored. [Offline report](verification/usb-clock-audit-offline-20261013.md). Physical clock/capability and verified SDK shutdown now pass, [board report](verification/usb-clock-audit-board-20261013.md). The exact `usb-host1` enumeration profile now passes the bounded RAM planner; physical EHCI/OHCI/root-hub/RDA enumeration and shared-clock removal/rebind now pass, [host report](verification/usb-host-board-20261013.md) |
| USB host0 enumeration image | Separate `usb-host1` kernel links with exact EHCI/OHCI/shared-clock DTS and no class/storage/network drivers. Actual resource/config mutation gates, image/layout and QEMU ARM observer/time64 pass locally; following physical clock/capability acceptance, the exact enumeration RAM plan also passes; [offline report](verification/usb-host-offline-20261013.md). Clean diagnostic CI including this image passed on `3355c5b`; physical clock/capability acceptance, EHCI/OHCI/root hubs, RDA 480-Mbps enumeration and seven shared-clock removal/rebind stages now pass, [host report](verification/usb-host-board-20261013.md). RDA firmware/radio remain pending |
| SP805 system restart | Original strict-ID candidate remains hardware unaccepted: the actual ID cells are zero. An exact native router RAM module checks measured MV100 SYSID0/inactive watchdog registers and rechecks them in its callback; actual helpers/module lifecycle/PTY guards pass. Graceful command restart, automatic CA-loader stop/inspection, two-CRC router retransfer, config/empty-password restoration and module reload now pass physically without a power cycle, [board report](verification/native-restart-board-20261013.md). Separate SD identification now also passes physical restart/shutdown and automatic router return; other profiles require matching integration |
| SD/TF | Native register audit and separate metadata identification pass. Dedicated `sd-ro1` now physically exposes `SU04G` SDHC,3965190144 bytes as a read-only block, discovers p1/p2, passes 4096-byte/overlap reads and VFAT read-only mount/360-byte existing-file read/unmount. Request-level write/erase/settings denial, measured shutdown and autonomous router return are enforced; IRQ Err0/RAM-file time64 pass. Actual policy/driver/queue/get_ro sanitizers, profile/layout/CRC, ARM-shell syntax, local builds, PTY and QEMU pass, [report](verification/sd-ro-board-20261013.md). Second partition filesystem, ext4/exFAT physical mounts, hotplug, production integration and writes remain pending |
| Wi-Fi | RDA USB `1e04:8888`; compatible-descriptor source pinned; complete USB module linked locally and in CI against separate Linux 6.12 config, manufacturing eFuse-write entry points excluded, key/WID sanitizer regression passed; [initial module report](verification/wifi-module-port-20261012.md); later control-response fixes and local sanitizer checks in [control report](verification/wifi-control-20261012.md); actual key callbacks now pass cipher/length/role/peer/RSC/MIC and firmware-error sanitizer checks, with AP-reset cache state gated on reply; [key report](verification/wifi-keys-20261013.md). Unimplemented iovar/key operations now return unsupported; existing AP-stop state changes wait for a successful reply, TX-power failures preserve cached/output state and BIP/WAPI capability declarations are removed; actual-function sanitizers and full module link pass locally, [operation report](verification/wifi-operations-20261013.md). Actual USB startup is blocked by missing named-roaming/capability transport; READY now rolls back on initialization failure, with real-function sanitizer and module link pass locally, [startup report](verification/wifi-startup-20261013.md). Directed scanning now retains the first firmware/wait failure, normalizes timeout errors and publishes wait state before requests; actual-function sanitizer/module/core checks pass locally, [scan report](verification/wifi-scan-20261013.md). Modern-kernel USB enumeration now passes, [host report](verification/usb-host-board-20261013.md). User reports RDA5995 marking; fixed physical USB identity queries now return state zero, while revision/firmware replies contain no WID/data; [query report](verification/rda-usb-identity-20261013.md). Revision, matching firmware and radio operation remain unverified |
| Official OpenWrt / Passwall | Pinned native GCC 14.3/musl 1.2.5 target and Passwall/Xray/LuCI pass isolated ARM QEMU time64, DNS/TLS, authenticated UI, SOCKS, fw4 and TCP/UDP TPROXY. Corrected application/Ethernet RAM boot now passes physical Ethernet/DHCP, authenticated local/host LuCI/Passwall UI and normal DNS/NTP. A bounded physical ARM/SoC namespace fixture also passes strict-CA HTTPS, VLESS/TLS SOCKS, forwarding and TCP/UDP TPROXY, [board report](verification/openwrt-router-board-20261013.md). External Ethernet forwarding/performance, Wi-Fi/AP and Docker remain pending |
| Application external-initrd RAM packaging | Both plain and integrated application images pass 512/240-MiB QEMU budgets and checked separate uImage/DTB plus bounded initrd at `0x04000000`. Payload/provenance/resource mutations and two-CRC UART gates pass. Integrated physical TFTP/boot is verified for the report's exact image; plain physical boot remains untested. Fresh Xray clock-corrected artifacts and actual provenance/console hashes were verified, [Xray report](verification/xray-browser-clock-20261013.md) |
| Applications/Ethernet RAM integration | Separate native router variant builds Passwall/Xray/LuCI, matching modules and measured Ethernet drivers. Both QEMU budgets pass Xray before NTP, NTP/time64, DNS/TLS/UI/SOCKS and fw4 TCP/UDP TPROXY. The corrected TX image now runs physically with DHCP, gateway, host UI and automatic DNS/NTP from its delivered peer-DNS default. Latest user RAM config/credentials were restored with all 15 file hashes checked. Physical ARM namespace forwarding/TCP/UDP proxy fixture passes again on this exact kernel and independently restores current config/temporary state; [board report](verification/openwrt-router-board-20261013.md). Sustained physical TCP passes with zero additional errors/drops/FIFO; external Ethernet routing/performance remain unverified. Storage/USB/Wi-Fi/SMP excluded |
| Pinned source download recovery | Diagnostic CI on `57a77c7` failed before compilation because the BusyBox HTTPS connection was refused. Bounded retry, SHA-preserving temporary publication, nine regression tests and a real fresh local download pass; [report](verification/source-download-20261013.md). The later complete `7bad089` [diagnostic run 38300887226](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38300887226) passed fresh download/build, all diagnostic profiles, Wi-Fi operation guards and uploads; the later READY rollback also passed the complete `fbc1e79` run 38304430531 |
| NTP protocol/time64 | Installed BusyBox client corrects four isolated loopback cases across 2036/2038 and from 2026 to 2040 in both plain/router QEMU budgets, [era report](verification/openwrt-ntp-time64-20261013.md). The delivered router peer-DNS default now passes a fresh physical RAM boot: DHCP resolver populated automatically and installed NTP set the normal current 2026 date without a manual clock command. The 2040 RAM-file probe still passes. No physical future wall clock was set; [board report](verification/openwrt-router-board-20261013.md) |
| Whole-system Y2038 | Not established; core, selected applications and one-shot NTP emulation passed. Persistent filesystems, other protocols and physical whole-system behavior remain unverified |
| LuCI Chinese default | Shared application/router configuration includes base/firewall/Passwall Chinese catalogues and defaults first boot to `zh_cn`. Actual installed files/packages, translated login labels and HTML language pass both QEMU budgets; backward RAM-artifact compatibility, evidence/payload/resource mutations and two-CRC gates pass. The exact Chinese image now runs physically after fresh inspection/TFTP/both-device-CRC gates; untouched first-boot language, current DNS/NTP/time64, restored 15 user files/password, authenticated Chinese Passwall UI and application namespace fixture all pass. Bidirectional physical TCP has zero additional error/drop/FIFO counts; cleanup/config preservation verified. [Chinese report](verification/luci-chinese-default-20261013.md), [board report](verification/openwrt-router-board-20261013.md). Fresh application CI pending; external routing and radio/AP remain separate |
| Xray + sing-box + unzip | Both plain/router variants explicitly include Xray 26.10.10, sing-box 1.14.3 and InfoZIP 6.0-r9. Actual ARM rootfs and both 512/240-MiB QEMU budgets pass Passwall-generated SOCKS/VLESS TLS for both cores, expired-certificate rejection, Chinese/empty-password login and ZIP64/Chinese/2040 extraction. Router fw4/netifd/Xray TCP/UDP TPROXY still passes. Selected sing-box omits Tailscale/ACME/gVisor while retaining QUIC/uTLS/WireGuard/Clash API. Pinned upstream libdeflate level 12 reduces initrds to 33291872/33408575 bytes; the interim 36-MiB cap is corrected to `min(32 MiB, 512 * 65535 - 1)`, expansion stays 96 MiB. Actual immutable snapshot/curl transfers pass with 512/1468-byte blocks; packaged candidates and resource/provenance/size/two-CRC mutation gates pass, [report](verification/passwall-dual-core-20261013.md). The exact final router now passes both physical device CRCs, Chinese/empty-root login, Xray/sing-box VLESS-TLS SOCKS, ZIP64/Chinese/2040 RAM extraction and namespace forwarding/Xray TCP/UDP TPROXY, with user configuration preserved. Plain physical boot and fresh CI remain pending |
| Docker package compilation | Separate official Docker/dockerd 29.6.1, containerd 2.2.5, runc 1.3.6 and tini 0.19.0 ARM APKs compile and pass actual package/staging equality, source/recipe hashes, EABI5, qemu-arm version and Linux/ARMv7 Go metadata checks. Version checks use real libc/libgcc1/libseccomp APK payloads. Compile-only kernel enables container dependency features but excludes board storage/network/USB/SMP; no boot/rootfs/daemon/container acceptance. [Report](verification/container-packages-20261013.md). The later standalone ARMv7 runtime passes overlay2/cgroups/seccomp/DNS/NAT/lifecycle/shutdown locally; [runtime report](verification/container-qemu-runtime-20261014.md). The independent combined native rootfs now passes actual procd/Docker/tini/fw4 networking, both container-namespace Passwall proxy cores, reload coexistence and graceful cleanup alongside the application/time64 suite, with 26 required markers and coherent export; [combined report](verification/container-applications-qemu-20261014.md). Physical Docker/eMMC and fresh runtime CI remain pending |
| Wi-Fi scan-result parsing | Actual NETINFO lengths and every IE are checked before publication; full SSIDs/rates and discard/error/list IE ownership pass real-function ASan/UBSan, complete ARM module link and core regression locally. [Report](verification/wifi-scan-results-20261013.md). Remote parser CI passed on `e52cfb5` with actual artifact verification; firmware transactions/radio and asynchronous teardown remain unverified; named-roaming/capability startup is still blocked |
| Wi-Fi association frames | Actual original STA-response/AP-request parser reproduces a short-frame ASan overflow. Patched actual standalone/native functions pass received-header/HT/fixed-field/IE bounds, prior-data preservation, replacement/empty IEs, station-allocation failure and ownership/lock checks. Full ARM module, native APK/ABI/eight broken-package guards and core build/time64 pass; actual manifest files and matching source verified. [Report](verification/wifi-association-frames-20261013.md). Standalone diagnostic CI on `45762c2` passes with actual files/patches/marker verified; native package CI on `918366f` also passes with all 17 actual files and source/log identities verified. The later native sanitizer CI, other association/event paths, concurrent teardown and physical STA/AP remain pending. Startup transport remains unsupported |
| Native OpenWrt RDA package | Separate native cfg80211/USB kernel and real APK compile locally with GCC 14/WERROR. Actual APK payload, USB alias, built-in symbol providers, stripped-module equality and exact kernel ABI pass; eight broken-package cases are rejected. Native package CI [38318338689](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38318338689) and standalone diagnostic CI [38318338712](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38318338712) passed on `5aa1af4`; downloaded manifests and actual log markers were verified, [report](verification/openwrt-wifi-package-20261013.md). No boot image, installation, host enumeration, firmware startup or radio acceptance |
| Wi-Fi chip-start queries | READY/revision now wait for acknowledged firmware-state/revision/version data; failures preserve errors and cached revision, with no u04 fallback. Actual startup/getter/wire-parser ASan/UBSan, complete standalone module, native APK/ABI/mutations and core lint/build/time64 checks pass locally. Diagnostic CI `38342674256` and native package CI `38342674314` passed on `6b53448`; downloaded manifest files, matching Git patches and actual sanitizer/package markers were verified, [report](verification/wifi-chip-start-20261013.md). Named roaming/capability transport and physical USB/firmware/radio remain unverified |
| QEMU application DNS handover | Later plain application CI [38318338793](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38318338793) on `5aa1af4` failed because the old dnsmasq had not released its port. The isolated fixture now bounds service-exit waiting and checks its replacement process. Plain/router runtime reruns pass both 512/240-MiB budgets, with console/provenance hashes verified, [report](verification/openwrt-dns-fixture-20261013.md). Fresh plain/router CI [38342674311](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38342674311) passed on `6b53448`; all four downloaded artifacts, actual console markers/hashes and exact Git fixture-source identities were independently verified. This QEMU fixture does not establish physical DNS/routing acceptance |

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
next work is RDA chip/firmware identification and radio/AP initialization,
external Ethernet routing, broader RAM/storage/SMP and Hinas compatibility.

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

Subsequent clean native package CI on `3e89e05` passed for both
[Docker packages](verification/container-packages-ci-20261013.md) and
[RDA module/APK](verification/openwrt-wifi-ci-latest-20261013.md).
All 13 container and 17 RDA downloaded manifest files, exact source identities
and actual log markers were independently verified. Physical Docker and Wi-Fi
firmware/radio remain unverified; the later isolated Docker QEMU runtime passes
locally and awaits fresh remote CI. The complete `7c4b816` diagnostic run
[38425001836](verification/diagnostic-sd-ci-20261013.md) also passed; 13 downloaded
manifests/130 declared files, twelve uImage checks and actual SD/Wi-Fi/Ethernet/
USB test markers were independently verified. Its pending native application/
core runs were replaced by newer `c7cec7e` runs. The clean dual-core
[application run 38415519493](verification/passwall-dual-core-ci-20261013.md)
on `3e89e05` also passed: four actual artifacts, six files per RAM variant,
both 512/240-MiB budgets, input/provenance/console hashes and actual
Xray/sing-box/unzip/Chinese/empty-root and router Xray TCP/UDP TPROXY
markers were independently verified. Sing-box TPROXY remains unverified.

The later diagnostic CI on `45762c2`,
[run 38374147701](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38374147701),
passes the USB enumeration RAM permission, association-frame bounds and serial
Unicode-display changes. Twelve downloaded manifests/119 declared files,
eleven uImage checks, exact Wi-Fi patches and actual sanitizer/USB/Ethernet
log markers were verified, [CI report](verification/diagnostic-ci-latest-20261013.md).
Native package/application runs remain separate. The additional pinned
[RDA source audit](verification/rda-startup-source-audit-20261013.md) found
no implemented named-iovar transport in three more driver directories;
chip/firmware identification and radio/AP initialization remain unfinished.

Serial collection now uses [the CLI workflow](docs/ttl-baseline.md), without
HiTool for routine UART access. Local validation is recorded in
[verification/serial-cli-20261012.md](verification/serial-cli-20261012.md).

The latest router RAM milestone corrects the clock/MAC/PHY board allowlists and
Xray startup before NTP synchronization. The independent Ethernet audit keeps
its original peer-DNS policy; the application router has its own DNS-enabled
DHCP-client selection. See the physical router report for exact booted identities
and the distinction between local SoC forwarding and external Ethernet routing.

The subsequent full diagnostic CI on `1ac00af`,
[38351038836](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38351038836),
passed. Its eleven downloaded manifests, all 109 listed files, ten kernel
image CRC/structure checks and actual Ethernet-probe/Wi-Fi/USB log markers
were independently verified; see the [probe report](verification/router-probe-guards-20261013.md).
This predates the later TX-backpressure correction and does not replace
integrated-application or physical acceptance.

The corresponding [application CI](verification/applications-probe-clock-ci-20261013.md)
on `1ac00af` also passed: all four downloaded artifacts, six files per RAM
variant, actual console/provenance hashes and fixed fixture inputs were
independently verified. It covers Xray startup before NTP and the delivered
peer-DNS default, and predates the TX correction and Chinese default.
