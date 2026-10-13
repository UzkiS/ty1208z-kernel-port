# Independent OpenWrt application validation

The `apps` subtarget builds actual ARMv7 musl packages and exercises Passwall
under a 2040 wall clock in isolated QEMU. The ordinary application build emits
a separate initrd and raw kernel. An additional `openwrt-app-ram` stage packages
that exact tested pair for experimental RAM transfer; it supplies no sysupgrade
or installation recipe. The plain `ram` target and standalone Linux diagnostic
remain independent.

## Fixed inputs

The base OpenWrt source and board/BusyBox patches come from the existing native
target. `openwrt/applications/sources.lock.json` fixes complete archives for
packages, LuCI, Passwall and Passwall packages by commit and SHA-256. Only the
selected package roots and their dependencies are installed into the build.
Passwall 26.10.4 selects Xray 26.10.10 and nftables; unused proxy engines and
geodata are explicitly disabled rather than included by default.

New application/router builds include the Simplified Chinese LuCI, firewall
and Passwall translations. A first-boot UCI default selects `zh_cn`; browser
language detection is not required. Users can change the language in LuCI
afterward. The built-rootfs checks require the language default, actual LMO
catalogues and installed translation packages.

The application build reuses the completed native GCC 14.3.0/musl 1.2.5
toolchain as an external compiler and records compiler/libc hashes. The pinned
Xray requires Go 1.27. A checked recipe patch selects the versioned Go 1.27.1
compiler already in the pinned packages feed; no moving Go download is added.
Kernel modules are built against this application kernel, not copied from
Hinas or the standalone diagnostic.

A checked Passwall Lua patch emits custom TLS CAs as Xray's required
`certificates` array. The pinned upstream emits an object and Xray rejects
that configuration. Original/patched hashes are locked, and the built gate
checks the actual installed Lua file. This preserves strict hostname and
certificate expiry validation.

## Reproduce

Use a regular Linux user and a Linux filesystem. Install the dependencies in
`.github/workflows/openwrt-applications.yml`, then run:

```sh
make openwrt-toolchain TASKBASE=/absolute/linux/build-root
make openwrt-app-config TASKBASE=/absolute/linux/build-root
make openwrt-applications TASKBASE=/absolute/linux/build-root
# Also exercise a 240-MiB usable budget and package the checked RAM candidate:
make openwrt-app-ram TASKBASE=/absolute/linux/build-root
```

The application source/build lives under `TASKBASE/applications/`. Downloads
are shared with the fixed base build; feeds and outputs remain separate. The
build checks feed/recipe identities, selected options, actual installed package
manifest and storage/hardware exclusions. QEMU gets no disk or host network.
Writes, the fixture password and future clock exist only in the RAM guest.

`checks/applications-qemu.json` records the exact kernel, config, initrd, package
manifest and console hashes, toolchain identity and passed runtime markers.
The clean GitHub workflow repeats the native toolchain build and application
acceptance. The [completed matrix report](../verification/openwrt-applications-ci-20261013.md)
records verified plain/integrated TCP and RAM-packaging acceptance on `62db42b`;
later UDP/NTP fixtures still require their own complete remote result.

## Runtime acceptance and limits

The fixture first tests the installed BusyBox NTP client against a bounded,
QEMU-only loopback server: 2036 era wrap, the signed 2038 boundary and correction
from 2026 to 2040 must produce the actual expected clock. Neither test helper
enters the delivered rootfs. Source/binary/shell hashes join the runtime
provenance; see the [NTP result](../verification/openwrt-ntp-time64-20261013.md).

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

Two local VLESS TLS servers then test Xray's own certificate handling at
2040. Passwall's custom-CA UCI option trusts the fixture CA; its real controller
starts the clients. HTTPS content must pass through the valid TLS server;
the expired proxy certificate must fail with Xray's certificate-expired log.
The fixture waits for Passwall's asynchronous boot handler to finish before
starting its instances, so a later service restart cannot erase their state.

nftables must count actual loopback packets and accept socket/TPROXY rules.
Inserting those expressions is not transparent-proxy forwarding acceptance.
The default QEMU test uses a Cortex-A7 with 512 MiB. The RAM stage repeats the
same application acceptance with 256 MiB and `mem=240M`, conservatively
accounting for the board's low-16-MiB allocation reservation. Neither trial is
a board memory/performance measurement. Ethernet, cold boot, WAN/LAN routing,
real Passwall TPROXY, physical clock/NTP service operation,
persistent filesystems, Wi-Fi and whole-system Y2038 remain separate gates.
See [the local result](../verification/openwrt-applications-20261012.md).

## Separate RAM packaging

The application archive is too large to embed while keeping the kernel's
decompressed image/BSS below the low-16-MiB boundary. `make_openwrt_apps_ram.py`
keeps the accepted raw kernel and its matching rootfs/modules unchanged and
adds an explicit chosen initrd range to a standalone board DTB. The archive
starts at `0x04000000`; its maximum compressed budget of 32 MiB ends below the
unexplained bootloader Bound Addr `0x08e62000`. This conservative placement does
not resolve the full memory map or establish a hardware boot.

The wrapper verifies the actual 240-MiB QEMU provenance, archive bounds,
critical board source identities, kernel layout and explicit peripheral-free
profile. `prepare_ram_boot.py` checks it against the recorded loader identity
and DDR response. The UART tool loads the kernel and initrd separately and
requires both device CRCs before sending the one measured `bootm` command.
Address/profile/provenance mutations and either CRC failure stop the flow.

The output is `artifacts/openwrt-apps-ram1/`, distinct from the native Ethernet
candidate. It has no board Ethernet/storage/USB or SMP support. The application
CI runs both memory trials and uploads the wrapper as HARDWARE-UNTESTED. The
actual local checks and limitations are recorded in the
[RAM packaging report](../verification/openwrt-apps-ram-offline-20261013.md).

A distinct [applications/Ethernet variant](openwrt-router.md) integrates the
measured drivers in its own source/build tree and exercises actual netifd/fw4
forwarding and Passwall TCP/UDP TPROXY in isolated QEMU network namespaces. The
plain application profile remains peripheral-free; physical integration
acceptance is still required for the Ethernet variant.
