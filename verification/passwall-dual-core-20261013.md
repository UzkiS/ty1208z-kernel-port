# Passwall dual cores and InfoZIP — 2026-10-13

Official OpenWrt `openwrt-25.12` remains pinned to
`58efa9917d4cc53fceed173529a286187649e827`. Passwall UI/control is from
`openwrt-passwall/openwrt-passwall` at `14b4ef0b`, version 26.10.4; both proxy
recipes come from `openwrt-passwall/openwrt-passwall-packages` at `1af0a5c4`.
The delivered cores are Xray 26.10.10 and sing-box 1.14.3. InfoZIP unzip
6.0-r9 comes from the pinned official packages feed. Kwrt customization has
been removed from the requested scope; the board's Linux support is retained.

## Actual native builds and runtime

Both plain and measured-Ethernet variants build with native GCC 14.3/musl 1.2.5.
The installed package manifest and actual rootfs contain both ARM cores and
the InfoZIP executable. Chinese base/firewall/Passwall catalogues and the
reviewed `zh_cn` first-boot default are installed. The root shadow password
field is empty; empty-password LuCI login reaches the actual Passwall page.
A separate guest-only password then exercises normal authentication.

Real Passwall UCI nodes generate, validate and start Xray and sing-box
configurations. Each core carries the exact loopback HTTPS payload through
SOCKS and VLESS/TLS at 2040. A trusted valid CA/hostname works; an expired
proxy certificate must produce the core's actual expiry error and must never
carry the payload. A bounded retry waits for that error rather than accepting
an unrelated connection failure. NTP era/time64, DNS, HTTPS and nft counters
also pass. The router variant separately retains real fw4/netifd forwarding
and Xray TCP/UDP TPROXY acceptance in isolated network namespaces; sing-box
TPROXY and board operation are not inferred from its SOCKS/TLS results.

The host-generated ZIP includes stored/deflated content, a Chinese pathname,
ZIP64 local headers, an empty file and a 2040 timestamp. The actual ARM unzip
tests and extracts it; all content SHA-256 checks and the epoch timestamp
match. Its hash is included in the runtime provenance. The QEMU machines have
no disks or host network; future clock changes and fixture passwords remain
inside the RAM guests.

| Variant | Compressed initrd bytes | Uncompressed bytes | uImage bytes | QEMU usable budgets |
|---|---:|---:|---:|---|
| applications | 33291872 | 92099072 | 3389828 | 512 / 240 MiB passed |
| router | 33408575 | 92375040 | 3437600 | 512 / 240 MiB passed |

## Memory boundary

The full-default sing-box build also passed the 512-MiB fixture, but its initrd
was 41313920 compressed / 110684160 uncompressed bytes. At 240 MiB, the kernel
reported an initramfs unpacking write error; it is not a bootable candidate.
Disabling only embedded Tailscale still produced 36378226 compressed bytes.
The selected RAM configuration disables Tailscale, ACME issuance and gVisor,
while retaining QUIC, uTLS, WireGuard and Clash API. The final recipe uses the
pinned upstream libdeflate 1.25 at gzip level 12 with a sorted reproducible
newc archive and no gzip timestamp. The compressor recipe/source and actual
raw/decompressed cpio equality pass before QEMU tests the final archive.

Both final variants passed independent Windows curl transfers of their actual
uImage/initrd snapshots at 512-byte blocks and negotiated 1468-byte blocks.
The router initrd uses 65252/22758 blocks respectively, safely below rollover.

An intermediate 36-MiB offline cap passed memory-layout/QEMU checks, but the
actual TFTP snapshot constructor rejected both 34.7/34.8-MB archives before
opening a socket. The existing transfer protocol requires fewer than 65535
512-byte blocks; memory fit alone was insufficient. The cap is restored to
`min(32 MiB, 512 * 65535 - 1)` (33553919 bytes). The final selected archives
pass both QEMU budgets and the actual immutable snapshot/independent curl
transfers, with and without negotiated options. Their range starts at
`0x04000000` and ends below `0x06000000`, below the observed but unexplained
bootloader Bound Addr `0x08e62000`. The 96-MiB expansion cap, low-16-MiB
kernel-footprint gate, exact-payload hashes, 240-MiB acceptance and two
independent device CRC gates remain enforced.
Actual resource/DT/provenance mutations pass; rehashed oversized compressed
and expanded archives, or removing all dual-core runtime evidence, are denied.
The earlier measured single-core artifacts remain accepted by their older
evidence without being relabeled as dual-core images.

The new RAM candidates have no persistent installation recipe and have not
booted on the box. The running Chinese system retains its existing credentials;
future new images default to root with an empty password. Docker remains
required work, with higher-memory, storage, container-kernel and actual ARMv7
container acceptance still pending. Wi-Fi firmware/startup and STA/AP also
remain pending. Compiled packages and QEMU success do not close those gates.

## Exact local identities

### applications

- `uImage-UNTESTED.bin`: `c8d222f1e706b823764acd36e3196737c45d918a0849628e228b769585fa7c49`
- `rootfs.cpio.gz`: `59146ee66dc60e2b1d4d0cdd6b56c13e2a9f6238b6e4c76e6368c6f486cd185f`
- `packages.manifest`: `57bd135fea3bd28efce3ac2299e9190a9856207ee8e5aee8e5022432d2698523`
- `sing-box-1.14.3-r1.apk`: 13634011 bytes, `d9028a816dcabd1470cf02377608ed4d3dbd8fe86a3c4ba2d5ccd8f8958262cf`
- `xray-core-26.10.10-r1.apk`: 12403367 bytes, `4bba547bc8fb11bac2ed4f4aea67d502b3ad9e00d3119bbab5cc51ea9f1ba343`
- `unzip-6.0-r9.apk`: 110394 bytes, `08beed8f654ab319edfd585ee93b2332acb3179de87585b09c023dfcb3542e27`
- QEMU 512 console: `23f157e5ec2e5e2659d9b60660c690cd4073d200c957b517fd05214b688c6470`
- QEMU 240 console: `c900da603d2b3f9fbe056602677c6446dcc409aa1dd14d09d0bd1f28dadf9d69`

### router

- `uImage-UNTESTED.bin`: `b62240f15eedb72f28faaf2f2c03f5c985c62c40d19a140b8ebd63828a7c2ecd`
- `rootfs.cpio.gz`: `8c9d99caed2a11bc1a8e3fdd7da3164496ba834d6a556c9240f4ec30f253a0b1`
- `packages.manifest`: `790817a699587e6e43fbf8f7e2e9cf1e71b7354f32087b35d9ade3b3d7239867`
- `sing-box-1.14.3-r1.apk`: 13634011 bytes, `d9028a816dcabd1470cf02377608ed4d3dbd8fe86a3c4ba2d5ccd8f8958262cf`
- `xray-core-26.10.10-r1.apk`: 12403367 bytes, `4bba547bc8fb11bac2ed4f4aea67d502b3ad9e00d3119bbab5cc51ea9f1ba343`
- `unzip-6.0-r9.apk`: 110394 bytes, `08beed8f654ab319edfd585ee93b2332acb3179de87585b09c023dfcb3542e27`
- QEMU 512 console: `bbb357fa5110c2acb23bf5b5c7e992a85fae12e55a08564af5ba9d3b33dab72a`
- QEMU 240 console: `74ddf3446e44e894d237c71e5ac3973fde5e4380564903ed5849058aa21807f8`

