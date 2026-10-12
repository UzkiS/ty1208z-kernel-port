# Native application/Ethernet RAM integration — 2026-10-13

Result: a separate native OpenWrt kernel/rootfs with Passwall/Xray/LuCI and the
measured Ethernet drivers built successfully. Actual netifd/fw4 forwarding and
Passwall TCP TPROXY HTTPS and bidirectional UDP delivery pass in isolated ARM
QEMU at 2040, under both 512 MiB
and 240 MiB usable-memory budgets. RAM packaging, resource/provenance mutations,
actual FEMAC sanitizer and UART CRC/identity checks pass locally.
**No physical boot or routing acceptance of this integrated candidate exists.**

## Local artifact identity

| File | Bytes | SHA-256 |
|---|---:|---|
| uImage | 3436528 | `33e303e41528d8eefd3c192d4fe1c9d2286d702222d41bf29479f4c22560d4c8` |
| Raw zImage | 3434152 | `84acedad14b63be8a20aaa7486186c9231586d905c7de690401596f30a291c0e` |
| Board DTB | 2312 | `70814cd4cc45e775e7251da48d262e8608369752fb76f6d4cb5d24501d4fa706` |
| rootfs.cpio.gz | 21044278 | `bca90c4678b8623446dcaf914a2dcb7d4e3409c2ef43e1e9dcc9248210310b0d` |
| Kernel config | 64994 | `c4cfccaaa15c6bc57e03713c822331728d529d53abf3a9ab00931edfd9e8ff96` |
| Package manifest | 4423 | `339fc1e806f1574275ba0e7aed3f5fc1a70b7a9c8f13ce4dda76625e25ea3f59` |
| 240-MiB QEMU console | 125688 | `3a3f11f69c15323d298a35d0d1746671178ccaff55e46c099ccf369608d06958` |

Kernel: `6.12.112-ty1208z-openwrt-router`, with measured CPU0/UART/timer/Ethernet
and its own native modules. Storage, USB, wireless, SMP, debugfs and untested
restart are excluded. Plain application/native Ethernet outputs stay separate.

Header/payload/entry: `0x01ffffc0` / `0x02000000` / `0x02000000`; BSS ends at
`0x009c0ac0`, below 16 MiB. Initrd starts at `0x04000000`, is 21044278 bytes
compressed and 54202880 bytes uncompressed, within 32/96-MiB budgets and below
unresolved loader Bound Addr `0x08e62000`. The plan against the actual recorded
loader inspection passes; uImage CRC32 is `ec63b002`, initrd CRC32 `b4eb4243`.
This is a placement candidate, not a complete map or physical transfer result.

## Actual runtime acceptance

Both trials use Cortex-A7/one CPU, no disks/host network; clock 2040 exists only
in the guest. Existing DNS, certificate rejection, HTTPS, authenticated LuCI/
Passwall/rpcd, generated Xray SOCKS/VLESS TLS and nft expression/counter markers
pass. Additional acceptance:

- `NTP_ERA_TIME64_PASS`: the actual installed one-shot BusyBox NTP client
  corrects the guest clock across 2036/2038 and from 2026 to 2040 against a
  QEMU-only loopback server. Both memory trials pass before the remaining
  application/router tests. See [NTP evidence and limits](openwrt-ntp-time64-20261013.md).

- `OPENWRT_ROUTER_FORWARDING_TIME64_PASS`: netifd links/routes, fw4 forwarding,
  actual namespace-client HTTPS traffic and nonzero forwarding counters.
- `PASSWALL_TPROXY_TCP_TIME64_PASS`: without forwarding, HTTPS fails; the
  installed Passwall service generates Xray, nft TPROXY and fwmark table 999,
  and the same request succeeds without SOCKS configuration. After service
  stop it fails again. Actual TPROXY counters increment. The proxy server is
  the fixture's isolated valid VLESS/TLS server.
- `PASSWALL_TPROXY_UDP_TIME64_PASS`: a real iperf3 server in the origin namespace
  receives bounded UDP through ordinary fw4 forwarding first. With forwarding
  removed, its TCP control connection fails. The installed Passwall service then
  enables UDP TPROXY to that origin through the valid VLESS/TLS node. Forward and
  reverse UDP transfers each report over 4096 received bytes and ten packets;
  the actual generated UDP TPROXY rule has a nonzero packet counter. After
  service stop, the control connection fails again. UDP load is limited to
  128 Kbit/s, 512-byte datagrams and three seconds per transfer. This establishes
  delivery through both proxy directions, not emulated or physical throughput.

Provenance binds exact kernel/config/rootfs/packages/console hashes, variant
and all markers. All three router markers are required for the Ethernet variant;
plain application acceptance cannot authorize an Ethernet kernel. Exact
hardware resources/connections use the same Ethernet policy, with modules/
netfilter/IPv6 permitted only for this separate application identity.

## Tooling and regression

The actual built FEMAC RX/ISR/NAPI/TX monitor passes ASan/UBSan. Critical board/
clock/PHY/helper sources match the overlay. Resource mutation tests initially
changed raw/empty-string FDT interpretations instead of actual typed cells;
they now mutate the fields consumed by the policy, including zero-valued
clock/size cells. Resource/config/provenance/address/two-CRC PTY cases pass.

The UART collector requires distinct `net`/`router` kernel/rootfs identities;
foreign identity, echo-only markers or missing binding fail before experiments.
Ordinary Ethernet profile restrictions are preserved. Plain application CRC/
profile and Ethernet helper/profile checks, `make lint`, serial checks, core
`make build` and `make test` pass locally.

CI now declares locked pyserial and preserves its interpreter across the
restricted host PATH. Plain/integrated builds have separate matrix jobs. This
integration has no completed CI acceptance yet. Native core/Ethernet CI passed
on `8415dec` in [run 38272805257](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38272805257).
Plain application build/512-MiB QEMU CI passed on `b563d60` in
[run 38278345386](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38278345386);
that workflow did not run external-initrd packaging. Diagnostic CI passed on
`62db42b` in [run 38287462061](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38287462061).
These results do not cover the new native integration/matrix or UDP fixture.

## Remaining acceptance

The pending physical boot remains the independent native Ethernet image. It
needs startup, sustained TCP/counters and cable recovery; the integrated image
then needs its own hardware boot/application/network checks. Emulated TCP/UDP
TPROXY does not establish physical speed/proxy behavior, physical NTP/clock operation, whole-system
Y2038, Hinas startup, full RAM/SMP, storage or RDA USB/radio operation. No flash,
persistent environment or security writes occurred.
