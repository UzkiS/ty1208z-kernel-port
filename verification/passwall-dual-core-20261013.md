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
| applications | 34703485 | 92099072 | 3389828 | 512 / 240 MiB passed |
| router | 34819844 | 92375040 | 3437600 | 512 / 240 MiB passed |

## Memory boundary

The full-default sing-box build also passed the 512-MiB fixture, but its initrd
was 41313920 compressed / 110684160 uncompressed bytes. At 240 MiB, the kernel
reported an initramfs unpacking write error; it is not a bootable candidate.
Disabling only embedded Tailscale still produced 36378226 compressed bytes.
The selected RAM configuration also disables ACME issuance and gVisor, while
retaining QUIC, uTLS, WireGuard and Clash API.

After the selected pair passed both QEMU budgets, the compressed cap was
reviewed from 32 to 36 MiB. Its maximum range is `0x04000000..0x06400000`,
below the observed but unexplained bootloader Bound Addr `0x08e62000`. The
96-MiB expansion cap, low-16-MiB kernel-footprint gate, exact-payload hashes,
240-MiB acceptance and two independent device CRC gates remain enforced.
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

- `uImage-UNTESTED.bin`: `fb4f29967746d83ec1eb1186f31f250c207c36fa95fb4da3b4bcfa1dbb08a936`
- `rootfs.cpio.gz`: `a5bb5fb86eb8c52a1a19d72aab660260c471ea9e2998005c21b8865fb902aade`
- `packages.manifest`: `891a7ce4220222a3312a95f24418ded38f94642428df1bf0c3298515a4097368`
- `sing-box-1.14.3-r1.apk`: 13634011 bytes, `d9028a816dcabd1470cf02377608ed4d3dbd8fe86a3c4ba2d5ccd8f8958262cf`
- `xray-core-26.10.10-r1.apk`: 12403367 bytes, `4bba547bc8fb11bac2ed4f4aea67d502b3ad9e00d3119bbab5cc51ea9f1ba343`
- `unzip-6.0-r9.apk`: 110394 bytes, `08beed8f654ab319edfd585ee93b2332acb3179de87585b09c023dfcb3542e27`
- QEMU 512 console: `347fcd6fc7e520ae66b91498386c2edf690b2c4d51bb02b8eca87eb2b1b2e252`
- QEMU -256 console: `050b8b89f00975e4cffa48252640c43324620d47a691c05dd3b647caacc0a24d`

### router

- `uImage-UNTESTED.bin`: `a26b7fe7bcc98973118f656e2541b69ba9bc7e6711fd1ec04d46709b45787b52`
- `rootfs.cpio.gz`: `6049af15e12cc9f07fb684b463c0ffdc6264fa8608af61953cbec7067d8df37b`
- `packages.manifest`: `6ab9256f94bfbd6b564ce05c7a263dc90db752ad6d221f7a7ea974e3d0383d15`
- `sing-box-1.14.3-r1.apk`: 13634011 bytes, `d9028a816dcabd1470cf02377608ed4d3dbd8fe86a3c4ba2d5ccd8f8958262cf`
- `xray-core-26.10.10-r1.apk`: 12403367 bytes, `4bba547bc8fb11bac2ed4f4aea67d502b3ad9e00d3119bbab5cc51ea9f1ba343`
- `unzip-6.0-r9.apk`: 110394 bytes, `08beed8f654ab319edfd585ee93b2332acb3179de87585b09c023dfcb3542e27`
- QEMU 512 console: `4a6ac81cfeb595d038f56fb419429483732a4f7c5c5ed14065ef39c927411fbf`
- QEMU -256 console: `e26de5210c4bcbdb94435fc304552c9a523493231d1b60a050af60c15cce484b`

