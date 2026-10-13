# Native router applications on physical TY1208Z

Date: 2026-10-13. The corrected native application/Ethernet candidate booted
from RAM through the original CA fastboot. Ethernet/DHCP, authenticated LuCI/
Passwall UI, Xray startup before clock synchronization and normal DNS/NTP
passed on the board. Actual Passwall forwarding/TCP/UDP TPROXY also passed
using local network namespaces on the physical ARM/SoC. Those namespace
tests do not establish external Ethernet forwarding or throughput.

## Booted image

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
default still needs a separate cold-boot check; the service evidence above
uses the equivalent runtime configuration on the booted image.

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
