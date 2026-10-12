# OpenWrt applications — local ARM QEMU acceptance

Date: 2026-10-12. No board transfer, storage writes or hardware operation.
The final local application build and runtime gates passed. Clean application
CI is configured but has not yet completed.

## Inputs and actual build

- Base OpenWrt: `58efa9917d4cc53fceed173529a286187649e827`.
- Packages: `54d77dd5714bb4747c4bf061735304d18076de0b`.
- LuCI: `8125d1288b359f6df505d3328b712bf059843fc8`.
- Passwall: `14b4ef0bcfeb8a01a22f70a3c4f01cdb87fd0b1d`, version 26.10.4.
- Passwall packages: `1af0a5c4fb3a227201683b64d32f61c65db9be72`.
- Native GCC 14.3.0/musl 1.2.5; Xray 26.10.10 built with Go 1.27.1.

Complete feed archives and the checked Xray recipe patch are locked in
`openwrt/applications/sources.lock.json`. The actual `apps` rootfs includes
LuCI, rpcd, Passwall/Xray, firewall4, dnsmasq-full and TLS/test utilities.
No hardware CA image or install recipe is emitted. The kernel keeps
SMP/BLOCK/MMC/MTD/USB disabled and does not enable the physical Ethernet driver.

The local native compiler SHA-256 is
`ca5e1fdba996f43813d8b0ec2f4a907bf683bd94c7932df1988ad8bced2ab84e`;
its musl libc SHA-256 is
`0e24069ac7b54a42a10616c6424577b944a888f54767990ce1ae973b1cfba239`.
These identify the local toolchain, not a promise that another host produces
identical binaries.

## Passed runtime

Diskless QEMU virt, Cortex-A7, one CPU, 512 MiB, no host network. The actual
native raw kernel and separate initrd are used. All fixture writes are in RAM.

```text
TIME64_PASS sizeof(time_t)=8 realtime=2208988800 file=2208988800
CERTIFICATE_TIME64_PASS
DNS_TIME64_PASS
HTTPS_TIME64_PASS
PASSWALL_LUCI_AUTH_TIME64_PASS
LUCI_RPCD_TIME64_PASS
PASSWALL_XRAY_SOCKS_TIME64_PASS
NFT_EXPRESSIONS_AND_COUNTER_PASS
Sun Jan  1 00:00:11 2040 user.notice time64: OPENWRT_APPLICATIONS_LOG_2040
OPENWRT_APPLICATIONS_QEMU_PASS
```

The certificate fixture creates a trusted CA spanning 2026 and 2040, an
expired 2026 leaf and a valid 2040 leaf. OpenSSL and actual curl/mbedTLS
accept the valid certificate and reject expired/untrusted HTTPS with code 60.
dnsmasq serves a local test name for default dual-stack curl resolution;
curl's selected threaded resolver is verified by its actual AsynchDNS feature.

LuCI returns the expected protected 403/login form before authentication.
The real HTTP login creates its session/cookie; the authenticated Passwall
page must return successfully and must not be the login form. The installed
Passwall controller generates and starts Xray from a UCI node. HTTPS traffic
passes through Xray SOCKS and the local upstream microsocks to uhttpd.
nftables counts real traffic; socket/TPROXY expression insertion also passes.

## Exact final local artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Raw application zImage | 3390152 | `4f4c44b7d59b2691a51c56aed552c15cbe590e56f82827b8ec77bdbd721ae7c1` |
| Separate rootfs cpio.gz | 20924863 | `49eec5fd6c4f647463370b3054fae6fa6263a260ce4e9eed68bd5bdb6b86075b` |
| Installed package manifest | 4344 | `13cd0e2446847582f0fef4532587178f69cd928a469c990e8bd71c94142a7223` |
| QEMU console | 24357 | `8ff31734c57f7e4c8628411451cf277da4b1b3a013c57025d897ac771e1c1fb0` |

The machine-readable provenance is saved beside the local outputs as
`checks/applications-qemu.json`. Binaries and raw logs remain excluded from Git.
The rootfs size includes verification utilities; no board footprint or final
production size is established.

## Issues resolved and remaining scope

The image dispatcher must run after OpenWrt's `image.mk` resolves SUBTARGET;
otherwise it silently emits the plain board image for the apps selection.
The built gate rejects any CA uImage in this application output. Long fixture
upload lines were truncated by BusyBox ash; commands now stay below 256 bytes.
dnsmasq's local-domain flag prevents an unsupported AAAA query from forwarding
to a nonexistent upstream. LuCI's protected login is checked explicitly, not
mistaken for an HTTP readiness failure.

An incremental curl configure changed the threaded-resolver option without
updating the library binary. A scoped package clean/rebuild corrected the
local artifact, and the guest now requires the selected runtime feature.

This result covers the selected applications at 2040 in emulation. It does
not establish MV100 Ethernet/USB/Wi-Fi, physical Passwall routing/TPROXY,
throughput, other proxy protocols, NTP, persistent storage, Hinas compatibility
or whole-system Y2038. Reproduce with `make openwrt-applications`; hardware
and installation must pass their separate gates.
