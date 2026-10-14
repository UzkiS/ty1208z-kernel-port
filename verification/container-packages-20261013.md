# 原生 Docker 软件包编译（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

This is a compile-only milestone. No board image/rootfs was emitted, no Docker
daemon or container was started, and no board memory, storage or networking
acceptance is inferred from the package checks.

The independent `openwrt-container-packages` entry uses official OpenWrt
`58efa9917d4cc53fceed173529a286187649e827` and official packages feed
`54d77dd5714bb4747c4bf061735304d18076de0b`. The five reviewed recipe/source
archive hashes are locked in `openwrt/containers/sources.lock.json`.

The native GCC 14.3/musl 1.2.5 build produced actual ARM EABI5 APKs. The checker
extracts each package and compares its executable with actual package staging,
checks architecture/package/source/recipe identities and runs only `--version`
through qemu-arm. The four Go binaries report Linux/ARM/GOARM=7; runc also
reports libseccomp 2.5.5. The version checks use the real libc, libgcc1 and
libseccomp APK payloads, since compile-only target staging has no installed
musl loader. The initial staging-only version attempt failed for that missing
loader; package-payload execution fixes the verification environment.

Packages remain `m`, with a separate dependency kernel enabling block support,
namespaces, cgroups, memcg and seccomp. MMC, MTD, USB, board Ethernet and SMP
remain excluded. Btrfs comes from the actual upstream containerd dependency;
it does not enable a board disk driver. Both application QEMU and RAM packaging
explicitly reject this compile-only source tree.

| Package | Actual APK version | APK bytes | APK SHA-256 |
|---|---|---:|---|
| docker | 29.6.1-r1 | 9664309 | `1a354cfa133c9dc7661b89a831ec4a6998b8f691ca73c30ce880c9042e1d65f5` |
| dockerd | 29.6.1-r1 | 26989170 | `6d2d972a4e20ecc6733946c91cf8d012fbc9b85d929edcea103bdcc94a1a697d` |
| containerd | 2.2.5-r1 | 33884192 | `34c11e5cae92dbc2720f924a917765847d0aea75dde159b33119351c63e95ec5` |
| runc | 1.3.6-r1 | 4503643 | `8fbe36c11cc014391b92991cda27f34edc652f2970e614e15ec5bdea72550a71` |
| tini | 0.19.0-r4 | 34047 | `78b5a776c5e24b8fe6c65be8b059ba01b4987b33767d1163abf0c29df263cab0` |

Docker remains required final work. Higher usable memory, real eMMC block I/O,
filesystem/recovery validation and a real ARMv7 container with networking,
resource limits and restart must pass separately. Persistent installation
retains its own authorization boundary. Clean container CI is pending.
