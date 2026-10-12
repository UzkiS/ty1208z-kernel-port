# Native OpenWrt RDA package experiment

`make openwrt-wifi-port` compiles the optional RDA USB driver through native
OpenWrt Kbuild and creates a real APK in its own build tree. Run
`make openwrt-toolchain` first. The entry reuses only the fixed native
GCC 14.3/musl toolchain, verified pinned source files and the same generated
driver patches as `make wifi-port`. The shared module object list belongs to
`wifi/Kbuild`. No firmware is fetched or packaged.

The ordinary diagnostic, Ethernet and application/router trees stay separate.
This entry delivers compile/package artifacts under `artifacts/openwrt-wifi-port`,
with no boot image or automatic module loading. It does not install the package,
touch the box or establish a working Wi-Fi interface.

## cfg80211 ownership

The locked OpenWrt `kmod-cfg80211` package uses wireless backports 6.18.55.
The existing RDA port targets native Linux 6.12 cfg80211. This experiment
therefore enables native `CONFIG_CFG80211=y` and USB in an independent kernel,
and explicitly excludes the backports cfg80211/mac80211 packages. Mixing the
two stacks or copying a module from the standalone kernel is unsupported.

The package has an exact dependency on its own native kernel/config ABI.
The checker reads the actual UTS release, kernel ABI hash, exported symbols,
ARM module/vermagic/USB alias, and APK metadata and extracted files. It compares
the packaged module with the actual linked module after OpenWrt's stripping
step. No module-load/firmware hooks or firmware/autoload files are allowed;
only standard OpenWrt package wrappers and the generated file inventory remain.
Extraction does not install or execute scripts.

Host controllers, storage, debugfs and SMP are disabled in this compile
experiment. A later bootable integration needs its own measured USB profile,
kernel/config/modules and RAM resource acceptance.

## Acceptance boundaries

The actual-APK regression rejects another kernel release/config ABI, an empty
kmod, stale module release, unreviewed firmware and automatic activation.
The independent CI workflow rebuilds the pinned native compiler and package
from a fresh checkout and uploads COMPILE-ONLY artifacts. Its actual outcome
is recorded separately from local builds.

RDA interface startup still fails on unsupported named roaming/capability
transactions. Chip revision, firmware transfer, scanning, association, AP and
performance remain unverified. Returning fabricated firmware capabilities or
success is not an acceptable replacement for measured protocol behavior.
