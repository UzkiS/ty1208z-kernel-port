# Native RDA package: independently verified latest completed CI

The [native package run 38415520027](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38415520027)
completed successfully on `3e89e05655edd749ae61683988e9ba44013fc24f`.
This is module/APK compilation and parser/package validation, not radio acceptance.

All 17 actual downloaded manifest files matched byte-count/SHA-256 checks.
The four checker/generator source hashes matched exact commit Git blobs.
Both patches, Kbuild, both source locks and the real package Makefile matched
that commit. The downloaded log contained anchored config/package success,
eight broken-APK rejection and actual native association-parser sanitizer markers:

- `OPENWRT_WIFI_CONFIG_PASS`
- `OPENWRT_WIFI_PACKAGE_PASS`
- `OPENWRT_WIFI_PACKAGE_GUARDS_PASS`
- `RDA_ASSOC_FRAMES_PASS`

The module package remains compile-only: no boot image, physical install,
matching firmware, startup transport or STA/AP acceptance. Other standalone
driver sanitizer checks retain their separate reports; this log does not claim
to have rerun them all against the native package tree.
