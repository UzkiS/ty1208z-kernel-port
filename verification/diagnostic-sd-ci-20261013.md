# 含 SD 只读审计的诊断 CI（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The [diagnostic run 38425001836](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38425001836)
completed successfully on `7c4b816fd9de593e4a55d08c4756a839017a18e8`.
The actual downloaded artifacts were independently verified after completion.

All 13 manifests and their 130 declared files matched byte counts/SHA-256.
All twelve ordinary uImages passed independent header/data CRC checks,
length/load/entry validation and exact zImage + appended-DTB equality.
The actual Wi-Fi patches matched exact commit Git blobs.

Downloaded SD logs contain actual probe sanitizer, compiled DT/config/RAM-plan
and QEMU success markers. Ethernet logs contain actual probe/datapath/TX tests;
USB host/clock-audit logs contain helper/probe/sequence/RAM/QEMU markers.
Wi-Fi logs contain all nine port/control/key/operations/startup/scan/chip/parser
sanitizer markers. The separate native application/RDA/container pipelines
retain their own results.

This run validates the standalone `sd-audit1` profile, not the later temporary
native SD module introduced in `c7cec7e`. Neither QEMU nor CI establishes SD
card identification, physical storage I/O or firmware/radio behavior. The native
module's physical register observation is recorded separately in the
[SD board report](sd-audit-board-20261013.md).
