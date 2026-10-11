# 离线验证记录

日期：2026-10-11。主机 WSL Ubuntu 24.04.4，ARM GCC 13.3、binutils 2.42，
交叉 glibc 2.39，QEMU 8.2.2。实际构建配置和哈希随产物保存。

云端干净环境的完整构建和回归也已通过：代码提交 `7b99fe6`，
[Actions run 38141542884](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38141542884)。
首轮发现产物检查目录未提前创建，修复后重跑通过。此后状态文档的修改不改变二进制。

## 已通过

- 固定 Linux 6.12.112 与 BusyBox 1.37.0 的压缩包 SHA-256。
- 单核配置和必需的 ARM、串口、GIC、板级定时器、initramfs、系统调用选项。
- 无 block、MMC、MTD、网络、USB 驱动；不能由这个诊断内核访问盒子的存储。
- uImage 的头/数据 CRC、ARM 类型、原始 zImage 头与长度、DTB 结构与拼接位置。
- BusyBox 与 probe 是 ARM32 静态 ELF，QEMU user 能执行。
- 同一个 raw zImage 在 QEMU virt 上进入自带 initramfs，挂载 proc/sys/dev/tmp，
  shell 可执行。虚拟设备树与真实 MV100 设备树不同。
- 2040 年 `clock_settime` / `clock_gettime` 读回、日期转换、单调时钟与睡眠。
- RAM 文件 `utimensat` / `stat` 读回 2208988800；BusyBox `date`、`touch` 和
  `stat` 的 access/modify/change 输出没有截断。

## 测试发现并修复

BusyBox 原版 `stat -c %Y` 将 time64 的 `st_mtime` 强转成 ARM32 的 `long`，
使 2040 年的 2208988800 显示为 -2085978496。内核与 libc probe 同时读回正确，
所以问题定位于用户空间格式化输出。补丁改为宽整数输出，并保留未来时间回归。

构建初期的精简配置还缺少 BusyBox installer、部分 applet 子选项和旧时间接口。
已补齐。启用兼容 32 位时间 syscall 允许 glibc 在较小时间值时使用兼容路径，
并不禁用 time64。glibc 的 2040 年测试实际需要宽时间路径。

## 仍需实机或后续系统验收

当前 QEMU 使用 `arch_sys_counter`，没有执行 MV100 板级计时器初始化。
本机 UART 时钟、GIC 和 timer 中断、RAM/安全保留区域、高安验签、SMP、eMMC、
PHY/DMA、USB 和无线均未因此得到验证。

现有 Hinas、OpenWrt/Kwrt 的 libc 和服务、Passwall、代理核心、DNS、NTP、证书、
持久文件系统时间及重启恢复均未验收。不能由这份报告宣称整机 2038 问题已解决。

复现入口：`make verify`。Actions 每次构建运行相同检查，日志位于其
`HARDWARE-UNTESTED` 产物；在主机或真实 Hinas 上不设置未来墙上时间。
