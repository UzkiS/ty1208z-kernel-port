# Independent OpenWrt application validation

The `apps` subtarget builds actual ARMv7 musl packages and exercises Passwall
under a 2040 wall clock in isolated QEMU. It emits a separate initrd and raw
kernel, with no CA uImage, sysupgrade or installation recipe. The plain `ram`
target and standalone Linux diagnostic remain independent.

## Fixed inputs

The base OpenWrt source and board/BusyBox patches come from the existing native
target. `openwrt/applications/sources.lock.json` fixes complete archives for
packages, LuCI, Passwall and Passwall packages by commit and SHA-256. Only the
selected package roots and their dependencies are installed into the build.
Passwall 26.10.4 selects Xray 26.10.10 and nftables; unused proxy engines and
geodata are explicitly disabled rather than included by default.

The application build reuses the completed native GCC 14.3.0/musl 1.2.5
toolchain as an external compiler and records compiler/libc hashes. The pinned
Xray requires Go 1.27. A checked recipe patch selects the versioned Go 1.27.1
compiler already in the pinned packages feed; no moving Go download is added.
Kernel modules are built against this application kernel, not copied from
Hinas or the standalone diagnostic.

## Reproduce

Use a regular Linux user and a Linux filesystem. Install the dependencies in
`.github/workflows/openwrt-applications.yml`, then run:

```sh
make openwrt-toolchain TASKBASE=/absolute/linux/build-root
make openwrt-app-config TASKBASE=/absolute/linux/build-root
make openwrt-applications TASKBASE=/absolute/linux/build-root
```

The application source/build lives under `TASKBASE/applications/`. Downloads
are shared with the fixed base build; feeds and outputs remain separate. The
build checks feed/recipe identities, selected options, actual installed package
manifest and storage/hardware exclusions. QEMU gets no disk or host network.
Writes, the fixture password and future clock exist only in the RAM guest.

`checks/applications-qemu.json` records the exact kernel, initrd, package
manifest and console hashes, toolchain identity and passed runtime markers.
The clean GitHub workflow repeats the native toolchain build and application
acceptance. Check its actual result before describing CI as passed.

## Runtime acceptance and limits

The fixture checks libc/file time64, logging, real dnsmasq resolution, OpenSSL
certificate validation and curl/mbedTLS HTTPS. It requires valid 2040 TLS to
work and expired/untrusted certificates to fail. It checks LuCI's protected
login response, real password login, authenticated Passwall page, rpcd session
creation and the installed Passwall Lua API.

A UCI Xray node points only to a local microsocks server. The installed
Passwall `app.sh run_socks` generates and starts the real Xray configuration;
an HTTPS payload must pass through that SOCKS chain. The pinned controller
ends with a conditional append and returns 1 for this loopback Xray node.
The fixture permits that known status only alongside config validation and
actual data flow. No controller or proxy stub is used.

nftables must count actual loopback packets and accept socket/TPROXY rules.
Inserting those expressions is not transparent-proxy forwarding acceptance.
QEMU uses a Cortex-A7 with 512 MiB, which is not a board memory/performance
measurement. Ethernet, cold boot, WAN/LAN routing, real Passwall TPROXY, NTP,
persistent filesystems, Wi-Fi and whole-system Y2038 remain separate gates.
See [the local result](../verification/openwrt-applications-20261012.md).
