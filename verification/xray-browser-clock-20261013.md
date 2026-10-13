# Xray startup before clock synchronization

Date: 2026-10-13. Physical router RAM boot revealed that the installed Xray
26.10.10 panicked during package initialization while the board clock was in
1970. `ChromeVersion()` returned a negative major version; client-hint GREASE
generation used a negative array index before `xray version` could run.
The original shell stream has SHA-256
`cb25294877e4a444a600e41a2a998baaaadc141a2a78562fb4f8a532553d61c0`.

The locked source patch clamps the generated Chrome major version to its
baseline, 144. Future version growth is preserved. No certificate-validation
or TLS policy is changed. The feed recipe, archive, patch and actual compiled
`common/utils/browser.go` identities are checked during preparation/build.

| Input | SHA-256 |
|---|---|
| Xray 26.10.10 archive | `bc4b3fbe9f2612a7e8b7fffd4b7195f00ad4aa28478f3621fce925cb6190c036` |
| Original browser source | `e7c8146627718c8b80f2bd353b1389f460b77810675f132bdbe933fbc665bc1c` |
| Corrected browser source | `80b1c8b639bd87818bc8fb5c2419e4afc256ada0d5838317cc368855226533bc` |
| Source patch | `2c1f712993966369eed5ae04ce86eed097b72bffe63e39299059f68f0a08be87` |

The actual browser generators and package initialization are tested with
clock and CPU-randomizer seams using the native build's Go 1.27 compiler and
disabled module networking. The original pinned archive reproduces the
1970 startup panic. The corrected source passes initialization and 256 seeds
at dates in 1969, 1970, 2026, 2040 and 9999, retaining future version growth.
The marker is `XRAY_BROWSER_CLOCK_PASS`.

The isolated ARM QEMU fixture also sets the guest clock to Unix zero and
executes the actual installed `xray version` before NTP/application tests.
`XRAY_UNSYNCHRONIZED_CLOCK_PASS` is required in recorded RAM provenance;
old application acceptance without this check no longer permits packaging.
The rebuilt router passes this check in both 512-MiB and 240-MiB trials,
followed by installed NTP era/time64, strict certificate rejection, DNS/TLS,
authenticated LuCI/Passwall, SOCKS, forwarding and TCP/UDP TPROXY acceptance.
Host clocks were not changed.

The corrected router rootfs is 21044898 bytes, CRC32 `fe3b2a46`, SHA-256
`8a4c9e0f4a77020443fc5f7c0838d259b892b45b6e96e827cb0292fbb4fd33c2`.
Its 240-MiB console is 126679 bytes, SHA-256
`bcc7bd20826a68266f079e716377164534cbb966ff09c968e0ba2a237334aac2`.
The plain application rebuild also passes both memory trials, packaging and
CRC/profile checks. Its rootfs is 20924393 bytes, SHA-256
`6156f5a47f26632b65f7569673b1a81338e8351ac314771b338b4973976184af`;
the 240-MiB console is 110997 bytes, SHA-256
`cbac02d0939931e6f359bfffe4e5001e44fdcbf57dfa09b6bf810e4cbd337f2b`.
Actual manifest payloads, both trials' provenance/console hashes and markers
were independently checked for both variants. The later peer-DNS router
rebuild passes the same checks and has a different rootfs/wrapper identity.

The corrected router's physical Xray command succeeded while the clock was
still in 1970; normal DNS/NTP later set the current date. The
[physical board report](openwrt-router-board-20261013.md) records the exact
booted image and separate real-ARM local forwarding/proxy fixture. External
Ethernet routing/performance, Wi-Fi and physical whole-system Y2038 remain
unverified. Fresh remote CI for these source corrections is pending.
