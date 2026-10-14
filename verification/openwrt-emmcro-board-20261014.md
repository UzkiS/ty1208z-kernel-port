# 原生只读 eMMC 与完整备份实测（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

2026-10-14: the native eMMC/network RAM image boots physically after command
restart, fresh CA-loader inspection and separate kernel/initrd device CRCs.
Board patch: `fcd4b485369de9d129983b549b8bc46dda1d685ef7a0de996c356257e82166bf`.
The older accepted standalone eMMC payload remains preserved separately.

Chinese authenticated LuCI, empty root password, 14 restored configuration
hashes, IRQ Err0 and the built-in eMMC restart binding pass. No ordinary
restart module is loaded. This storage experiment temporarily uses low256;
the measured larger-memory system remains the basis for later integration.

The `008G30` user area reports 7818182656 bytes and nine read-only partitions.
Block/overlap/end, original kernel header and ext4 superblock reads pass.
An existing 444-byte file is read through ext4 `ro,noload`; the mount is removed.
Physical Ethernet transfers 32 MiB each way with matching hashes, no additional
errors/drops and RAM-file cleanup. No card writes, journal replay or repair.

Both QEMU budgets pass Chinese/empty-root, Xray/sing-box, unzip and time64.
Prior physical memory/application evidence is reused without repeating those
suites. Actual native config excludes OpenWrt block throttling and DT partition
parsing, retaining the measured command-line layout.

A private full user-area backup completed: 7818182656 bytes, successful SSH exit
and host readback SHA-256
`471a3b80e55c44823c601e4918504fa2977665021d8e36fcda7b79d185dc0695`.
Boot0/boot1/RPMB are excluded. The existing controller then performed one
guarded command restart, verified native eMMC shutdown and fresh CA loader,
transferred the exact original router with both device CRCs, and restored it.
Chinese authenticated LuCI, empty root password, all 14 configuration hashes,
restart binding and IRQ Err0 pass after return. No manual power cycle or
persistent/card write occurred. Physical Docker, Wi-Fi and installation remain
pending; their prior emulation evidence does not establish physical acceptance.
