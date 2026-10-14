# 原生路由应用与网口实测（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Date: 2026-10-13. The corrected native application/Ethernet candidate booted
from RAM through the original CA fastboot. Ethernet/DHCP, authenticated LuCI/
Passwall UI, Xray startup before clock synchronization and normal DNS/NTP
passed on the board. Actual Passwall forwarding/TCP/UDP TPROXY also passed
using local network namespaces on the physical ARM/SoC. Those namespace
tests do not establish external Ethernet forwarding or throughput.

## Initial booted image

| Item | Bytes / value | SHA-256 |
|---|---|---|
| uImage | 3436480; device CRC32 `c018fe3f` | `12b75e8e5e1ceb5e01f13e3c6448704c84b93c574432431becc7709ea4d356ce` |
| External initrd | 21044898; device CRC32 `fe3b2a46` | `8a4c9e0f4a77020443fc5f7c0838d259b892b45b6e96e827cb0292fbb4fd33c2` |
| Raw kernel | 3434104 | `66bccd7a93e17ea6bc260ccf4dcfb5a602cabe1332c43a152917099847507527` |
| Kernel release | `6.12.112` | Native rootfs target `hi3798mv100/apps` |
| DT compatible | `tianyi,ty1208z-ca-openwrt-router-ram` | Pinned source revision verified separately |

Fresh loader commands, DDR bounds and original boot path were checked.
Windows served two immutable TFTP snapshots with negotiated 1468-byte blocks.
Each server receipt, loader `filesize` and device CRC matched its corresponding
payload. Temporary loader networking was restored and read back before boot.
No flash, persistent boot, fuse/OTP or security-state write was issued.

The [probe correction](router-probe-guards-20261013.md) allowed the router
identity through the three exact resource/board probes. The clock gate passed
after TFTP without a policy change: CRG51 enabled to `0xb`, inherited PHY
controls passed, and FESTAv220 ID `0x20669823` bound at address 1. eth0 reached
100 Mbps/full duplex. netifd acquired a DHCP lease, gateway ping passed 4/4,
and the RAM-file probe reported eight-byte `time_t` and timestamp `2208988800`.
The RAM profile still generates a temporary MAC; leases can differ between
boots. Initial TX drop/FIFO counters retain the separately identified BUSY
accounting defect; this report does not claim zero-drop acceptance.

## Services and normal clock synchronization

At about one minute after boot the system clock was still in 1970. The actual
installed Xray 26.10.10, built with Go 1.27.1, ran successfully at that time.
The [browser-clock fix](xray-browser-clock-20261013.md) therefore has physical
startup evidence, independent of its synthetic-clock and QEMU checks.
Boot time defaults to Unix zero without a usable RTC; time64 support does not
supply the current date.

The inherited audit configuration had `network.probe.peerdns=0`. DHCP succeeded
but the active resolver list was empty, so the default NTP hostnames could not
resolve. Enabling peer DNS in the RAM configuration populated the resolver and
made a pool hostname resolve through installed dnsmasq. The already running
BusyBox NTP service then set the normal current date, 2026-10-13, matching the
host date. No manual date command, future wall clock or host-clock change was
used. The board's 2040 RAM-file round trip still passed after synchronization.

A random temporary root password was set only in this diskless RAM system.
Local unauthenticated LuCI returned 403 with its login form. Authentication
returned a session cookie, and the Passwall page returned its actual content
without the login form. A firewall rule restricted management to the test
computer. The same unauthenticated/authenticated checks passed across physical
Ethernet from that computer. Passwords, session cookies, MACs and personal
paths are excluded from this report and from tracked artifacts.

The router build now has its own DHCP-client configuration with peer DNS
enabled. Its rebuilt kernel/initrd, installed network bytes, both QEMU budgets
and packaging/profile/CRC checks pass. The resulting wrapper differs from the
booted wrapper because the external-initrd length changed. This delivered DNS
default received its separate cold-boot acceptance in the later TX image
below; the earlier service evidence above used a runtime configuration.

## Physical ARM application and forwarding fixture

A bounded fixture used only RAM files, generated test certificates and local
namespace endpoints. It checked the actual router DT/release, normal 2026
clock and disabled Passwall state before starting. Transfer hashes matched.
The long UART transfer stopped before execution; authenticated SSH completed
the same fixed script over the working Ethernet connection. No external proxy,
user subscription or WAN endpoint was used.

The actual installed applications passed:

- HTTPS with the generated CA; an untrusted certificate failed with curl 60.
- Passwall-generated Xray SOCKS through a local VLESS/TLS server with custom
  CA and hostname validation enabled; the real payload arrived.
- netifd-configured client/origin links and fw4 forwarding; HTTPS succeeded
  and the forwarding counter recorded 16 packets.
- With direct forwarding removed, HTTPS and the UDP test's TCP control
  connection failed. Starting the installed Passwall service then delivered
  HTTPS plus forward/reverse bounded UDP through TCP/UDP TPROXY.
- Actual TPROXY counters recorded TCP 3 packets/180 bytes and UDP 96 packets/
  50824 bytes. Policy rule/table 999 existed. Each UDP direction exceeded
  4096 received bytes and ten packets. After stopping Passwall, the direct
  requests failed again.

All seven physical fixture/completion/cleanup markers appeared and the script
exited zero. Network, firewall and Passwall configurations matched their
saved RAM snapshots afterward; fixture namespaces and counter table were
removed, Passwall returned to disabled, management remained reachable and the
normal date/2040 RAM-file probe passed. The ordinary Passwall stop path retains
an inactive `inet passwall` table; it is not an active proxy service.

These are real hardware executions of kernel/applications with veth endpoints,
not a two-port or VLAN Ethernet routing test. Wired forwarding/performance,
USB, RDA firmware/radio, SMP, persistent storage and whole-system Y2038 remain
separate milestones.

## Evidence identities

Raw streams and credentials stay in ignored local evidence.

| Observation | SHA-256 |
|---|---|
| TFTP and corrected RAM boot | `b71b458abce3da015913b787d40b07c852a3f0629a94c623994d9706c8d961c3` |
| Initial shell/Xray at 1970 | `7d593576b4230d74c93781b2c06cde66036b6b73b1db656162556473703ca1b3` |
| Fixed Ethernet collector | `c27d8073d17b68ed3bba77c9e9228d05b1b708ca84e346faa830fa977b223089` |
| Local authenticated UI | `b6c0ddf16bb48caa0a47888923e489736c8345f77d076092ee2e4cc8cccd8f8e` |
| DNS and normal NTP observation | `69962990eb7d8592eece2ed4192adb9ed0b1bb90d295f009338ad1c6cc6cc566` |
| Fixed physical application fixture source | `8569126d9b669b1db3105e52cc4cdf066505da8fd9a8c1ee2c1059856833ce0f` |
| Actual physical fixture output | `9d64a2996b0fdbbadacd216943cb10485039341b5637f0e9c3919facb3aadb09` |
| Post-fixture identity/time64 output | `cc65b9df1f8618c60dff579339333f9cf2abb07cf4b3da83124a9fc356c77dde` |
| Configuration/table cleanup checks | `6d59b9c119ffe7496f58bd348d7bcbc69a09cf5b94677ca449237c725b1944e4` |

UART produced no further echo after the interrupted transfer while Ethernet,
SSH and LuCI continued working. PL011 counters remained TX 47498/RX 23911
across the subsequent observations. This isolates the symptom from a board
crash but does not establish whether it originates in the TTL adapter, Windows
serial path or board UART; no guessed UART/clock register change was made.

## Later corrected-TX image and cold-default acceptance

The earlier corrected physical RAM image contains the
[FEMAC BUSY accounting correction](femac-xmit-20261013.md) and delivered
peer-DNS default. It supersedes the initial image for the checks in this
section; the Chinese image below supersedes it as the current runtime image.

| Payload | Bytes | SHA-256 | Device CRC32 |
|---|---:|---|---|
| uImage | 3436544 | `84a4abd0ce8877bed213f97475adf23cab5f6a7cf9e03c57ecff71b3ee44d18f` | `5d9e16b0` |
| External initrd | 21045256 | `abaf0f42801d72ee350eaed080c4bd017f2616f87e6616230fbf4fd169b2452f` | `79944e6b` |

The actual rebuilt FEMAC source is byte-equal to the checked generator result,
SHA-256 `241e02357337d81575a09d2abac0da85732f250fe6dab2b324155c997bfc588f`.
The booted raw zImage is
`329b834337b842113001984da7d13b16f601aed49694da89e5bdc79aeeeafab2`.
Fresh CA inspection, two TFTP receipts/sizes/device CRCs and temporary-loader
network restoration passed again. Native release/target/revision/router DT,
PHY ID/address/link, DHCP and 4/4 gateway replies were checked.

Before restoring user configuration, the untouched delivered network showed
`network.probe.peerdns='1'` and the automatically supplied gateway resolver.
The installed NTP service synchronized the current 2026 date without a manual
clock change; the 2040 RAM-file round trip and Xray version passed. This closes
the delivered peer-DNS cold-boot check. All 15 latest pre-reboot user files
were then restored and independently hash-verified, retaining fresh RAM SSH
server keys. Authenticated host LuCI passed again. Credentials remain private.

Corrected-image sustained TCP received 643956736 bytes host-to-board and
644481024 bytes board-to-host. All error/drop/FIFO/carrier counter increments
were zero; cumulative TX drop was 3 before and after. Its earlier cause is
unknown. The detailed clock/path/accounting limits are in the TX report.

The physical ARM namespace fixture was rerun against this exact kernel. All
seven completion/cleanup markers and exit zero passed, including strict-CA
HTTPS, VLESS/TLS SOCKS, fw4 forwarding and TCP/UDP TPROXY. Forwarding counted
16 packets/1353 bytes; TPROXY counted TCP 3/180 and UDP 96/50824. The fixture
used a new snapshot of the current user network/firewall/Passwall files.
Independent post-run hashes, saved `ip_forward`, absence of test namespaces
and removal of its counter table all matched. Passwall returned to disabled.

The Windows serial issue recurred with pyserial RX zero. A bounded local
`.NET System.IO.Ports.SerialPort` bridge immediately received the stopped
`fastboot#` prompt and completed fresh inspection, both TFTP/CRC gates, boot
and native shell interaction. Later serial timeouts still occurred, while
SSH/LuCI remained usable; COM9 was released and Ethernet used for follow-up.
This alternative working path does not establish a single serial root cause.

| Later evidence | SHA-256 |
|---|---|
| Exact new TFTP/boot stream | `b891e380672c86a24a981b008e3a790b0be7e2fcfff16fb9c1e37033b6e7bde6` |
| Untouched DNS/NTP default | `594cf3b148d9acbd991dd0a1ecab026d371ba5817d1b2d5e234a46a46e2081dc` |
| Latest user restoration record | `9b645764e6a0c70b47e1c6a63acf4b25fcbb30a8ad6f726bff6f8bbc2b97bc13` |
| Corrected physical fixture source | `0db56700c3c05615999ee95a5b6ea9c218b2c3a3d43cfe92ff3d2e62b627b8fb` |
| Actual corrected-image fixture stream | `5ea854f6fc203fcf3c6c93e64d8c421484861a02954e76ac941576fe1ede7696` |
| Post-fixture identity/time64 | `ee585c46c14bc21a79e5f1d86356a783e331eaabab6cf650f779ba412652142b` |
| Independent configuration/table cleanup | `8b672e816d66d30c1b1432e49c053407ebe6dd316a49806e1ee5d941c1c32c75` |

Full physical DDR is 1 GiB; the experimental image still exposes only low
256 MiB with low 16 MiB reserved. Higher memory, external Ethernet routing,
USB/Wi-Fi/AP, storage, SMP and optional Docker remain separate milestones.

## Current Chinese RAM image

The separately packaged [Chinese default](luci-chinese-default-20261013.md)
image now runs physically. Its raw zImage remains the corrected TX kernel
above; the wrapper DTB accounts for the larger translated initrd.

| Payload | Bytes | SHA-256 | Device CRC32 |
|---|---:|---|---|
| uImage | 3436544 | `80bcfbf09f329ad96ed7fd2de44fb946f8822b99b7af53979cc9de8054e1c3c4` | `9d11beca` |
| External initrd | 21142267 | `5d355a83991dc858643244bb635e517444f0d42e40f8836eea0e2eb384b258f7` | `3ff40518` |

The user identified a dropped serial 3.3-V supply during the intervening
garbled attempts, restored it and stopped at fastboot. The .NET bridge then
completed fresh loader inspection, both TFTP receipts/filesizes/device CRCs,
temporary-loader network restoration, boot and native console interaction.
This identifies the cause of those garbled attempts; earlier pyserial RX-zero
observations are kept separate. COM9 is released for follow-up over SSH.

Before restoring user configuration, the fresh delivered image reported
`zh_cn`, all three translation catalogues, peer-DNS enabled and an automatic
DHCP resolver. Normal current 2026 NTP synchronization, 4/4 gateway replies,
FESTAv220 100-Mbps full-duplex link and RAM-file time64 passed. Latest saved
user config/password/authorized keys were restored with all 15 file hashes
verified; fresh RAM SSH host keys were retained. After restoration LuCI was
set to Chinese. Authenticated host Passwall UI passed; credentials are private.

The physical ARM namespace fixture completed all seven required markers and
exit zero again. HTTPS validated its local CA, VLESS/TLS SOCKS worked, SoC
forwarding counted 19 packets/1501 bytes, and TCP/UDP TPROXY counted 3/180
and 96/50824. Independent cleanup verified the saved network/firewall/Passwall
hashes and `ip_forward`, no test namespaces/table, and Passwall disabled.
These are local namespace endpoints, not external Ethernet routing evidence.

Actual bidirectional physical Ethernet TCP received 650903552 bytes
host-to-board and 651689984 bytes board-to-host. Every error/drop/FIFO/carrier
counter increment was zero; initial cumulative TX drop remained 3. Board to
Windows monotonic elapsed ratios were 1.000053/1.000096. The temporary
source-restricted input rule was removed, user config hashes matched, and
gateway/time64 checks passed afterward. The host WLAN/WSL-NAT path and WSL
clock behavior still prevent treating this as an external routing benchmark.

| Chinese-image evidence | Bytes where recorded | SHA-256 |
|---|---:|---|
| TFTP/boot stream | 10115 | `f4c1f2a054d132cdc672e58615302ce51cd61cb56fb3d5df40b22d34ca81e03f` |
| Native console/default language/setup stream (private) | 4580 | `58ea1b2cbc4b2885bb6b8795bae4d5779be31b1058d7ed24310d5454152d39eb` |
| Untouched DNS/NTP default | — | `c30c6dd86b1861f06990a3f2ce209ca31516857d6740bbf4255c12764d6b2a83` |
| Restoration record | — | `b62c4e289ec8ba4fe6535e7a8ea77c6e2620041c1a81a9cf406bb654c4b5cbfa` |
| Language/catalogues/time64 | — | `7a694b729de84281907cc31feda1c0dd1cdc7819d6c1c2e37e476851f73ed96d` |
| Application fixture stream | 1301 | `1360c1b7327041dd9ee7dfe4cdc0a5d06381864f814eb24f0d06aaadd0808553` |
| Post-fixture identity/time64 | — | `315039dfd98f8cb7c5829c17c38925fa8142f06d231431ffdb944e4800dc56b9` |
| Independent fixture cleanup | — | `8b672e816d66d30c1b1432e49c053407ebe6dd316a49806e1ee5d941c1c32c75` |
| Bidirectional TCP record | — | `09ae76fc706b1f32a7b4c62dea28fc03d321e8c62fa6a08e6485df12251f2be6` |
| Post-TCP config/gateway/time64 | — | `184a7a68e5f7e59d0049ec2dd17f761c0758051aeacb36360be4f38a169b27ea` |
| Final online identity/gateway/time64 | — | `b461e85963be8d9f2346952baf1944699e201416f89e777de4dfda9ba557705b` |

Actual stored capture lengths/hashes, image identities, fixture markers and
both TCP client/server hashes were independently checked. USB/RDA enumeration
has separate [physical acceptance](usb-host-board-20261013.md); this running
router image still excludes USB/Wi-Fi. Radio/AP, broader RAM, storage/SMP,
external routing and installation remain unverified.

The final online check again passed Chinese login labels, native identity,
4/4 gateway replies and time64. The independent fixture-cleanup hash still
matched, with no test namespace/table and Passwall disabled as restored.
