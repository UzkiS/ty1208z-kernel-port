# Integrated native RAM system

The board kernel combines measured low-768-MiB memory, native Ethernet,
request-level read-only SD/eMMC, Docker kernel support and a restart handler
that requires both controllers to be quiescent. The native userspace includes
Chinese LuCI, an empty root password, Passwall with Xray and sing-box, unzip
and Docker. USB/Wi-Fi and persistent installation remain unfinished.

Build the pinned native toolchain, `openwrt-router-emmcro` userspace and
`openwrt-container-applications` userspace first. Their accepted application
evidence is reused. On Linux, the integration entry is:

```sh
make openwrt-system TASKBASE=/path/to/existing/taskbase
```

The build tool reads the native source from
`TASKBASE/router-emmc/build/openwrt-ram-<pinned-commit>`; `--native-source`
can select another explicit baseline. `openwrt/system/kernel.config` records
the exact configuration delta. The existing native compiler is checked by
`toolchain_from_native`; no foreign target modules are used. The tools work
only on build directories and artifacts and never access a physical device.

The packager places the matching modules directly under
`/lib/modules/6.12.112/`, because OpenWrt ubox kmodloader does not recurse into
`kernel/`. The bootstrap fits the measured transfer/expansion limits; an SSH
stream supplies the larger userspace supplement. Its first-boot defaults add
the single DHCP interface `probe` to WAN, Docker's zone and Docker-to-WAN
forwarding. The physical check used these UCI settings on the running board.

`--resume` reuses an inspected build directory. Packaging refuses a completed
output instead of silently replacing its delivery manifest; choose a fresh
`--output`/`--work` when retaining a completed artifact. The package database
still describes the bootstrap, so the supplement is a development delivery,
not an installable image. Booting requires fresh guarded-restart allocation
evidence, both board CRCs and the exact `system` profile. See the
[physical report](../../verification/openwrt-system-board-20261014.md).
