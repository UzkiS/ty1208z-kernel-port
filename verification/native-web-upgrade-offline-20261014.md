# 原生 sysupgrade 后端离线验证（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

2026-10-14：原生网页升级后端保留中文、Docker 和应用数据。
本轮实现使用固定官方 LuCI 的“系统 → 备份与更新”、官方固件校验 RPC、
`/sbin/sysupgrade`、procd 和官方 RAM stage2。没有新增独立升级页面。

板级 APK `ty1208z-upgrade` 提供 `platform_check_image` / `platform_do_upgrade`，
普通只读 RAM 系统不会包含该包；可写持久候选会安装它。既有首次完整安装的
内核、镜像和正在运行的刷写任务没有被替换。

## 格式与更新范围

上传包为有 fwtool 板型元数据的 ustar，固定包含 `manifest`、`kernel` 和
`rootfs.tar.gz` 三个成员。清单绑定精确 p6/p9 布局、长度、SHA-256 和内核 APK ABI。
根归档限制为 `bin etc init lib sbin usr var www`；禁止路径穿越、重复路径、
符号链接父目录、设备节点、hardlink 和 PAX。不包含 `/opt/docker` 或用户数据目录。

更新阶段先确认旧 p9 已被官方 stage2 释放，包括各进程 mountinfo、root/cwd/exe、
映射、fd、swap、block holders 和 loop backing files。随后在 p9 的独立目录暂存
完整新根，sync、清缓存并逐文件比较归档与读回内容。配置选项沿用官方备份，
受信任的 `/etc` 备份覆盖暂存配置后才切换受管系统目录。

旧系统目录和上一份 p6 留在事务目录中；p6 最后写入，按末尾扇区补零后做精确
SHA-256 读回并锁回只读，随后官方 stage2 重启。正常启动的清理服务才移除旧系统。
失败不继续自动重启；保留事务 receipt，不能宣称这是抗断电双系统更新。

## 已测结果

- 静态 ARMv7 helper 和真实 APK 成功编译；APK 依赖精确 kernel ABI。
- 实际升级包约 125 MiB；暂存空间保守计算约 358 MiB，另要求 192 MiB 余量。
- 实际 host ASan/UBSan 解析器、ARM 解析器、uImage CRC 和暂存文件读回通过。
- 错误板型、损坏内核、截断归档、路径穿越、Docker 目录覆盖、重复路径、
  hardlink、符号链接父目录和暂存文件损坏被拒绝。
- 官方 ARM 固件校验 RPC / `sysupgrade --test` 在隔离 QEMU 中通过，
  错误板型使用 `--force --test` 仍被拒绝。QEMU 的板型、分区、mount 和空间事实
  明确是合成 fixture；无磁盘、无网络，不作为实机存储证据。

实机安装仍在执行，网页上传、RAM pivot/完整卸载、真实 p9 激活、p6 读回、
自动重启和 Docker 数据保留尚未验收。当前不是“网页升级已经完成”的报告。
已有中文、无线、代理核心和 Docker 功能证据复用，不重跑功能矩阵。

## 本地入口

`tools/prepare_native_upgrade.py` 从受检的私有磁盘候选生成新 APK、根归档和
`ty1208z-ca-sysupgrade-UNTESTED.bin`，拒绝覆盖已存在输出。镜像含用户原厂
RDA 固件，只在本地保留，不上传仓库。

`tools/test_native_upgrade.py` 检查实际归档、ARM helper 和异常格式；
`tools/test_native_upgrade_qemu.py` 运行固定官方 ARM 升级校验器，报告中明确列出
合成事实和未证明事项。后续实机验收只覆盖新增升级边界。
