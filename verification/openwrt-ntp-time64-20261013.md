# Installed OpenWrt NTP client across the 2036 and 2038 boundaries

Date: 2026-10-13. This is isolated ARM QEMU acceptance; no physical box clock,
storage, bootloader, environment or security state was changed.

## Scope and implementation

The actual plain applications and integrated Ethernet/application rootfs use
BusyBox 1.37.0 `/usr/sbin/ntpd`, with `CONFIG_NTPD=y`, exposed through OpenWrt's
`sysntpd` service. The fixture stops that background service and waits for its
process to exit, then runs the installed client with `-n -q -p 127.0.0.1`.
There is no replacement or stub client.

`tools/ntp-qemu-fixture.c` compiles statically with the same pinned native
ARM/musl compiler as each image. It requires the QEMU virt compatible string,
binds only IPv4 loopback UDP/123, accepts only four fixed epochs and implements
standard NTP server replies, echoing the client's origin timestamp. Wire seconds
wrap modulo 2^32; the reference advances with monotonic time rather than the
guest wall clock being corrected. Lifetime and packet count are bounded.

The server and shell helper are injected through the QEMU console into RAM;
neither is packaged into the delivered rootfs. The build checker requires the
actual BusyBox client/service and rejects those fixture names in the rootfs.
QEMU exposes neither disks nor a host network. The ordinary board collectors
continue to leave the physical wall clock unchanged.

## Runtime gates

Every case requires the installed client to exit successfully, a real fixture
reply, zero rejected requests, and the observed wall time between the target
epoch and target plus 40 seconds. The seed must be earlier than the target.

| Case | Seed Unix seconds | Target Unix seconds | NTP wire seconds at target |
|---|---:|---:|---:|
| Before 2036 era wrap | 2085978100 | 2085978400 | 4294967200 |
| Cross 2036 era wrap | 2085978296 | 2085978596 | 100 |
| Cross signed 32-bit Unix boundary | 2147483468 | 2147483768 | 61505272 |
| Set 2040 from 2026 | 1791676800 | 2208988800 | 123010304 |

The final marker is `NTP_ERA_TIME64_PASS`. Afterward, the existing fixture
recreates its certificates and repeats the actual DNS/TLS/LuCI/rpcd/Passwall
SOCKS/VLESS TLS checks at 2040. The Ethernet variant also repeats netifd/fw4
forwarding and bidirectional TCP/UDP TPROXY acceptance.

The initial trial corrected its first epoch but failed the server's arbitrary
three-reply requirement: this installed client completed with two replies.
Acceptance now uses the client's successful status, actual clock correction
and a positive reply count, instead of prescribing its internal sample count.
This fixed the fixture; no production ntpd patch was needed.

## Evidence and limits

Both variants pass with a Cortex-A7, one CPU, 512 MiB, and separately 256 MiB
with `mem=240M`. Kernel/config/rootfs/packages/console and test input hashes
are recorded in each QEMU provenance file. The checked RAM packaging requires
the NTP marker alongside the existing application markers; missing-marker
mutations are rejected.

| Variant / usable memory | Console bytes | Console SHA-256 |
|---|---:|---|
| Plain / 512 MiB | 109953 | `19d28d395baaf731552c416adeac2d491d29ee7b2cf1c62d5dd0d0e768688cd2` |
| Plain / 240 MiB | 109927 | `15144e88881579db3b61bc2922b161c49a43203ae69c0389838722aa79fdb587` |
| Ethernet applications / 512 MiB | 125664 | `ae19a683e8d99d507ab2f46af84dc37f910bc9aeda21997b5e32a300a79ad847` |
| Ethernet applications / 240 MiB | 125688 | `3a3f11f69c15323d298a35d0d1746671178ccaff55e46c099ccf369608d06958` |

The static ARM server is 42056 bytes, SHA-256
`0a4c01000f2be6d3891b670a2bc17576cd9301478841ea7e5c6d9989a2f42d0f`.
The kernel/rootfs identities in the existing RAM reports stay unchanged; only
test provenance and console evidence changed. Packaging, required-marker
mutations and the real two-CRC PTY integration pass for both variants. Windows
copies pass actual-pair/resource/provenance checks; PTY cases run on Linux.
`make lint`, the ordinary diagnostic `make build` and `make test` also pass.

The application workflow includes this fixture in both matrix jobs and memory
trials. Complete remote acceptance now passed on `c25f83d`,
[run 38298432025](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38298432025).
Both actual jobs/all steps, uploaded image/provenance/console hashes, the
four corrected epochs/reply counts in all four trials and test-source hashes
against that commit were inspected. Remote identities are recorded separately
in [the CI report](openwrt-applications-ci-20261013.md).

These results establish the installed client's one-shot protocol/clock handling
in those scenarios. Physical clock accuracy, real network NTP servers, normal
procd/hotplug lifecycle and long-running frequency discipline remain untested.
Other protocols, persistent filesystems and whole-system Y2038 are separate
acceptance requirements. The candidates remain hardware-untested RAM images;
this report does not authorize installation or establish a finished router.
