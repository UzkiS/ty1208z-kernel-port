# TY1208Z CA 持久安装与升级

更新于 2026-10-15。紧凑网页首刷已经完成：1 GiB p9 全部 SHA-256 读回、p6 内核读回、
实际 eMMC ext4 rw 根启动和在线扩容均通过。p9 现为 1,752,576 个 4096 B block，
完整容量 6846 MiB，实机约 6.5 GiB 总空间、6.2 GiB 可用。配置和 Docker 容器内容
跨断电保留，Docker 冷启动自动运行通过。最新带挂载管理、USB 存储和普通重启修复的
镜像已通过官方 LuCI 保留配置升级，配置与 Docker 数据保留、冷启动自启、中文挂载页
和一次普通命令重启均实机通过。详见[升级实机报告](../verification/native-web-upgrade-board-20261015.md)。

## 安装范围与恢复

安装目标仅为 p6/p9。p6 起点 28672、长度 40960 个
512 B 扇区；p9 起点 1249280、长度 14020608 个扇区。保留 p1–p5、p7/p8、已知成功的
CA fastboot、持久 boot 环境、SD、boot0/boot1/RPMB 和安全状态。生产系统的 SD 支持普通单块/多块读写；只读诊断镜像仍拒绝写请求。

完整 eMMC 用户区 7,818,182,656 B 和原 p6 20 MiB 恢复镜像已私有备份，
长度及 SHA-256 核验结果保存在对应私有清单，安装前应核对自己的精确设备备份。
备份不含 boot0/boot1/RPMB，安装不修改这些区域。整盘恢复工具已准备，完整原系统
写回没有再作破坏性实测。

## 首次安装

TTL 发命令、网线 TFTP 启动专用 RAM OpenWrt，再在官方中文 LuCI“系统 → 备份与更新”
上传 first-install 包。无需 SD，不修改持久启动设置。安装器核对精确 RAM 内核、
eMMC 身份/容量、固定 p6/p9 布局、未挂载和其他设备只读。顺序为写入 1 GiB p9 →
flush/完整读回 → 恢复所选配置 → p6 写入/读回/只读锁定 → 官方 stage2 重启。
首次持久启动使用现有 p6 加载命令，在线扩容 ext4 到完整 p9。

实测首刷 p9 写入约 29 分钟、读回约 11 分钟；这些是旧单扇区版本的历史耗时，
不能代表新多块队列性能。网页本身不会改变控制器的 PIO/25 MHz 边界；紧凑包避免重复写完全部 6.7 GiB 空间。旧整 p9 writer 在
5,149,818,880 B 后已中止并锁回只读，自动续跑停止，后由完整紧凑安装替换。

最新 first-install 包包含扩容、Docker 冷启动、挂载组件和重启修复，未再次执行整个首刷；
沿用已通过的流程并记录改变的边界。详见[首刷报告](../verification/compact-first-install-board-20261014.md)。

## 后续原生网页升级

使用官方 LuCI“系统 → 备份与更新”和 `/sbin/sysupgrade`；板级 APK 提供
`/lib/upgrade/platform.sh`、校验器和受限 p6/p9 后端。上传后检查设备、布局、uImage
CRC、哈希和空间；官方 stage2 停服务、切 RAM、确认 p9 已释放后才更新。

采用文件级 staging 和逐文件读回核验，再激活受管系统目录、写入/读回 p6。
`/opt/docker`、`/root`、`/home`、`/mnt` 和 `/srv` 保留；勾选“保留配置”时恢复
官方配置备份。取消该选项会使用镜像默认配置，Docker 数据仍保留。正常启动回收旧系统
staging 并保留小型完成记录。失败保留 RAM 串口恢复，不盲目重启。

最新 sysupgrade 包：131,379,402 B；SHA-256
`b0f21dd0865677eba39b2b85e78784f66c9f93a428f4230de57055b433d9bf28`。
内核 4,925,410 B，SHA-256
`c2b72c4dd56705a93ead0d54a3151d3f1dbe934e0938d1ea5632743c109f135c`，
ABI `6.12.112~0757bd0e5fb295b399d4be7ea0c4decb-r1`。
镜像含经项目所有者授权的 RDA 固件；公开 Release 同时附带 `firmware/rda5995/` 和哈希清单。

## 安装修复

- resize2fs 只读打开已挂载块设备检查，对挂载点执行在线扩容 ioctl；不放开 raw mounted write。
- 核对 `/dev/root` 指向 p9；禁止 erase 的控制器不再宣告 discard/WRITE_ZEROES，ext4 使用受限普通写入。
- procd 注册 Docker 前预读 containerd，避开慢存储冷加载触发其 15 秒 deadline，并提供有界重试。
- 持久根重启保留仍挂载的 gendisk，MMC host 空闲后屏蔽 IRQ、关闭 PIO 时钟；新内核一次普通磁盘根重启已实机通过。

复用既有内存、无线、代理核心和 Docker 功能验收，只检查新安装/升级/重启边界。

最新内核另含 NTFS3。约 58.2 GiB 的 USB2 U 盘已通过 VFAT 与 NTFS 主分区只读文件访问和卸载；
NTFS 检查前后写入计数不变。未格式化、修复或更改分区，未保存自动挂载设置。
详见 [USB 实机报告](../verification/usb-storage-board-20261015.md)。
