# Integrated native RAM system

The board kernel combines measured low-768-MiB memory, native Ethernet,
request-level read-only SD/eMMC, Docker kernel support and a restart handler
that requires both controllers to be quiescent. The native userspace includes
Chinese LuCI, an empty root password, Passwall with Xray and sing-box, unzip,
Docker and Chinese Dockerman. RDA5995 WPA2 client and AP operation, netifd
role switching and the RDA LuCI form now pass their integration checks.
Storage writes and persistent installation remain unfinished.

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
`--output`/`--work` when retaining a completed artifact. The supplement now uses
a real offline APK transaction, with every module owned by a package from this
exact board build. It remains a RAM development delivery, not an installable
image. Booting requires fresh guarded-restart allocation
evidence, both board CRCs and the exact `system` profile. See the
[physical report](../../verification/openwrt-system-board-20261014.md) and
[wireless report](../../verification/rda-wireless-board-20261014.md).

`wireless/rda.sh` owns the one radio's daemon and module lifetime. It loads
the STA or AP firmware from user space, rather than re-enumerating USB while
cfg80211 holds RTNL. Supported settings are one AP or routed STA, 2.4 GHz,
HT20/legacy, open or WPA2-PSK/CCMP, and a fixed AP channel. The radio defaults
to disabled and contains no private test credentials. Checked transformations
in `tools/luci_rda_wireless.py` and `tools/netifd_wireless_eof.py` adapt the pinned
official UI and terminate handler discovery at EOF. Original vendor firmware
comes from the user's private backup and must not be redistributed.

The separate `build_native_system.py --persistent-candidate` build uses an
independent output tree and permits only measured p6/p9 sector writes.
`prepare_native_disk_root.py` creates the private full ext4 p9 and disk-root
uImage from those exact kernel/APK files; it never opens a device.
The ordinary RAM profile rejects this write-capable kernel. Only explicit
authorized installation mode may load it. The default invocation of
`probe_native_emmc_write.py` prints a one-sector write/readback/restore plan;
`--apply` is reserved for specific user storage-write authorization.
See [installation preparation](../../docs/installation-plan.md).

The specifically authorized last-sector probe now passes on the board, with
the original content restored and an automatic return to the readonly RAM
system/configuration; [physical report](../../verification/native-emmc-write-board-20261014.md).
The candidate exposes a page-sized block queue while upstream MMC data preparation
still trims every transfer to one sector. `install_native_emmc.py` defaults to
a verified offline plan, writes only fixed p9 then p6 under separately authorized
`--apply`, clears the block cache for SHA-256 readback and relocks each partition.
Its `--mode restore` streams only the original backed-up p9 range and p6 payload.
Full installation, recovery writes and disk-root boot remain unaccepted.

## Official web sysupgrade

The persistent candidate installs `ty1208z-upgrade` as a real APK. It supplies the board's `/lib/upgrade/platform.sh`, so the standard LuCI **System → Backup / Flash Firmware** page and `/sbin/sysupgrade` validation path are used. Uploads are metadata checked, bound to the measured p6/p9 layout, and rejected before any write when the board, uImage CRC, root archive or free-space check differs. Stage2 pivots to RAM, verifies that no process, namespace, loop device or swap still references p9, then stages the new root on p9 and updates p6 with exact readback before the official reboot.

The firmware archive contains only managed system paths. `/opt` (including Docker's `/opt/docker`), `/root`, `/home`, `/mnt` and `/srv` remain on p9 and are never replaced by the archive. LuCI's **Keep settings** choice restores the trusted configuration backup into the staged `/etc`; cancelling it resets configuration to image defaults while keeping data directories. An incomplete transaction leaves a receipt for recovery instead of silently deleting the old root.

## Compact RAM first installation

`make openwrt-first-install` builds a private first-install image from an existing
upgraded root and the exact disk-root kernel. Set `NATIVE_SOURCE`, `UPGRADED_ROOT`,
`DISK_ROOT` and `OUTPUT` when those prepared inputs use other directories.
The accompanying `ty1208z-first-install` APK is only for the temporary RAM system;
it enables the same official LuCI upload and sysupgrade/stage2 path for first use.
This image writes a 1-GiB ext4 p9, verifies it before activating p6, and carries
`ty1208z-firstboot-grow` to expand p9 on its first disk boot. Subsequent upgrades
use the separate file-level image above, preserving Docker and user directories.
See the [physical checkpoint](../../verification/compact-first-install-board-20261014.md).
