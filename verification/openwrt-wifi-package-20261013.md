# Native OpenWrt RDA compile/package acceptance, 2026-10-13

The independent `make openwrt-wifi-port` entry compiles the real RDA USB module
through the pinned native OpenWrt kernel/toolchain and produces an actual APK.
Local kernel/module linking, extracted-package/ABI checks and eight broken-APK
rejection cases pass. This is compile/package acceptance, not a working Wi-Fi
interface, a bootable delivery or permission to install.

## Independent stack and source ownership

This optional tree uses native Linux 6.12 cfg80211 built in. The locked
OpenWrt backports 6.18.55 cfg80211/mac80211 packages are excluded. The driver
uses the same 48 pinned source inputs, generated USB/API patches and shared
`wifi/Kbuild` as the standalone port. Unexpected cached inputs or symlinks
are rejected; no firmware is downloaded or packaged.

Native cfg80211's newly reachable configuration choices are explicit,
including signed regulatory-database verification and kernel keys. OpenWrt's
`MODULE_STRIPPED` setting is disabled in this tree so real USB alias/dependency
metadata remains available. Debugfs, host controllers, storage and SMP stay
disabled. The ordinary diagnostic, Ethernet and application/router profiles
remain independent.

The GCC 14 native build exposed old missing declarations, file-local helpers
with external linkage, optional unused helpers and a redefinition of the
native compat-task macro. Shared NVRAM declarations now have a project-owned
header; the packet-type declaration is available to the configurations that
compile its implementation. Audited file-local functions use static linkage,
optional helpers are annotated, and the obsolete compat-task override is
removed. The generator rejects changed anchors and external references to
the localized helpers. `CONFIG_WERROR=y` remains enabled in the native kernel.
These changes do not implement firmware transactions or radio capability.

## Actual built package

The actual ARM module has the locked USB alias and no manufacturing eFuse-write
symbols. Its imports all exist in the matching kernel's `Module.symvers` and
are provided by built-in `vmlinux`, so the APK does not silently depend on
another unlisted kernel module. Release/vermagic and the exact kernel/config
ABI dependency were read from actual generated files and APK metadata.

APK extraction does not install or execute its scripts. It contains exactly
the stripped module and OpenWrt's generated file inventory. Standard OpenWrt
package wrappers remain; custom hooks, firmware and modules.d activation files
are rejected. The payload matches package staging and the actual linked module
after the pinned OpenWrt strip step, including its kallsyms name-preservation
policy.

| Local artifact | Bytes | SHA-256 |
|---|---:|---|
| Actual APK | 140134 | `b99f2ee07f724e7ab8c28c3edbbd62cbabb4c1a0aa4aaddf78be98395723f862` |
| Packaged ARM module | 355992 | `9d0fa4591f1b3c7a2da95e8dd9f6ab9fe2857f5084665dd3150aaf416cce0289` |
| Native Linux config | 65463 | `3633b19aef667a67d53a0e92c3428f70670ce31fd54c140329eff7de8f1c2693` |
| Shared port patch | 112184 | `4fa37b6c9b527500c0da946381d2e22ffca692ccab58d1fa78e35c1b6bc6b9ac` |
| Standalone module after declaration/linkage changes | 322680 | `6085bdf396e9a4515d4bb049666fd23e79c2d4d91bdebc9f1f1b55e91573ab71` |

Native release is `6.12.112`; vermagic is
`6.12.112 mod_unload ARMv7 p2v8 `.
The APK version is `6.12.112.1-r1`, with exact dependency
`kernel=6.12.112~d16c03293ab72d701652b784b169e892-r1`.
The standalone module instead uses `6.12.112-ty1208z-wifi-port`; its kernel and
module must not be substituted into the native package.

## Verification and remaining work

Actual-APK mutations reject another release, another config ABI, a custom
module-load installation hook, a storage-enabled kernel, an empty kmod,
unreviewed firmware, automatic module loading and stale packaged vermagic.
The unchanged real APK passes again afterward. All prior real-function
WID/key/operation/startup/scan/result ASan/UBSan fixtures and complete
standalone ARM module linking pass with the shared source changes. Core
`make lint`, `make build` and `make test` pass, including QEMU time64 and RAM
boot/TFTP regressions.

The separate read-only, pinned-action native-package CI workflow rebuilds the
fixed native compiler and the package from a fresh checkout. Its result is
pending; the earlier successful parser diagnostic run excludes these new
declaration/linkage and packaging changes.

No module/image has been loaded on the box during this work. Hardware USB
audit/enumeration, actual RDA revision/firmware identity, named roaming/PHY
initialization, scan/association/AP, performance and Wi-Fi time64 behavior
remain unverified. The actual unsupported initialization rollback still
passes and still blocks interface startup. Physical native OpenWrt and routing
acceptance also remain outstanding.
