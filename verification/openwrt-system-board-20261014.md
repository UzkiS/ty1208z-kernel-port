# Integrated native OpenWrt: physical Docker acceptance

The single RAM system physically runs the native ARMv7 Docker 29.6.1 daemon
and a small container through OpenWrt procd, overlay2, cgroup v2 and default
seccomp. Container DNS through the LAN gateway and a TCP/HTTP request through
the physical Ethernet interface pass. SD/eMMC remain request-level read-only;
no card, flash or persistent boot writes occurred.

## Measured delivery

- Board: TY1208Z CA / Hi3798MV100, one online Cortex-A7 CPU.
- Kernel: Linux 6.12.112, SHA-256
  `b474bd8fc834cc8e9091159fe81855f46e63e4c70aef368cb3a324626d4b3ac4`.
- Resolved config SHA-256:
  `cce1bcb5838add7f35d31a3485c0b8f62aabe9bfbbb6ab81c4aa71db0f28a163`.
- Bootstrap: 22561748 compressed / 61516800 expanded bytes, SHA-256
  `3202c092c7e4305bb45e6e69bd992e3abdd6a19584763f85b3009ff102519b27`.
- Usable RAM: 762296 KiB, approximately 744 MiB. The low 16 MiB remain reserved
  and the upper 256 MiB excluded using fresh guarded-restart allocation evidence.
- eMMC `008G30`: 7818182656 bytes, nine partitions, read-only.
- SD `SU04G`: 3965190144 bytes, two partitions, read-only.
- Both storage controllers and the built-in guarded restart handler bind.
  Interrupt error count is zero.

Chinese/empty-root settings and application/runtime file identities were
checked during setup. The already accepted Xray/sing-box, unzip, time64,
application networking and higher-memory tests were reused rather than repeated.
The larger userspace supplement was streamed directly over SSH into RAM.

## Integration fixes and physical result

The initial system put modules in `lib/modules/6.12.112/kernel/...`.
OpenWrt's ubox kmodloader only scans the release directory itself. Flattening
the 107 matching modules fixes loading; no other target's modules were copied.

The daemon then started and ran a container, but forwarded DNS was rejected:
the DHCP interface `probe` was absent from the WAN zone and Docker had no
Docker-to-WAN forwarding. Adding the actual uplink to WAN and that forwarding
fixes the path while retaining the firewall. The target defaults in
`openwrt/system/docker-network` contain those settings.

The final physical check observed overlay2 on tmpfs, ARMv7, a 64-MiB memory
limit, CPU quota readback of `50000 100000`, PID 1 inside the container and
seccomp mode 2. It then resolved `openwrt.org` through the gateway and fetched
a unique HTTP token from the host over physical Ethernet. The final private
runtime stream SHA-256 is
`204a15c7108cac6659895628cba0b8a6b9a045424b500d2d448ec625b69a1675`.
The complete failed attempts were retained locally before cleanup.

After removing the container and stopping Docker, the three original UCI
files were restored. Both MMC hosts shut down, one command restart reached a
fresh CA loader, and both original-router device CRCs passed. The current
configuration, Chinese authenticated LuCI, empty root password, restart module
and IRQ Err0 passed after return. Restart stream SHA-256:
`2b3073766e7b7ecbc56d295311addc533f3c66e49a369ac4489b7437432eb193`.
Restored-router health stream SHA-256:
`30513a1cddf4eb8d0240e00279afa970d8a670e28640e8df4afe4d6586f02369`.
COM9 is released; no manual power cycle was needed.

## Reproducible source entry and remaining work

`make openwrt-system` now compiles/composes the native integration from explicit
existing pinned native build inputs. The normal build and packager completed;
the resolved config is byte-identical to the physical run. The rebuilt kernel
has a different build timestamp/version, SHA-256
`67716ef7f13b6f2f089b3fdcafe34937418026a984ee76c714c4b823d52a44f8`;
this rebuilt delivery and the installed first-boot defaults have not been
booted as a new exact artifact. They are not described as another measured pass.

The supplement still lacks final APK database registration. Storage-backed
Docker, installation/recovery images, RDA firmware startup and STA/AP operation
remain unfinished. This check does not establish registry downloads, general
Internet routing, IPv6 or performance. The ordinary restored router remains
the low256 RAM profile; no installation image is claimed.
