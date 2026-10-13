# Native Docker package compilation: verified CI artifacts

The clean [container package run 38415520188](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38415520188)
completed successfully on `3e89e05655edd749ae61683988e9ba44013fc24f`.
This verifies compilation/provenance and ARM executable version checks only.
No daemon, container or physical storage/runtime acceptance is claimed.

The actual downloaded manifest and all 13 declared files matched independent
byte-count/SHA-256 checks: five Docker APKs, three runtime library APKs and five
configuration/source/toolchain records. Package/source/recipe identities matched
the exact commit's lock; three check/build source hashes matched actual Git blobs.
Each recorded executable version and Linux/ARMv7 Go setting matched its package.
The actual CI log contains the anchored
`OPENWRT_CONTAINER_PACKAGES_PASS actual-native-APK ARM-EABI5 versions; daemon/container untested`.

| Package | Verified version |
|---|---|
| docker / dockerd | 29.6.1 |
| containerd | 2.2.5 |
| runc | 1.3.6 |
| tini | 0.19.0 |

Runtime remains dependent on measured higher memory, storage and container-kernel
support. Later commits and their Actions results remain separate.
