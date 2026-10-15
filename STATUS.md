# 当前状态与验收边界

更新于 2026-10-15。当前交付已完成 TY1208Z CA 实机 eMMC 安装和原生网页升级。
本页只记录当前集成状态；独立实验的当时结论见[历史验证索引](verification/README.md)。

## 已完成

| 项目 | 当前结果与证据 |
|---|---|
| 系统来源 | 官方 OpenWrt 25.12 固定 `58efa9917d4cc53fceed173529a286187649e827`，Linux 6.12.112；固定版本构建，不持续追踪 master |
| 首次安装 | TTL/TFTP 启动专用 RAM 环境，官方中文 LuCI 首刷；1 GiB p9 和 p6 完整读回，eMMC ext4 rw 根启动；[记录](verification/compact-first-install-board-20261014.md) |
| 容量与持久化 | p9 在线扩至 6846 MiB，文件系统约 6.5 GiB；配置和容器内容跨断电保留；[安装说明](docs/installation-plan.md) |
| 后续升级与重启 | 官方 LuCI 保留配置升级、stage2 RAM pivot、文件级根更新、p6 读回、默认 eMMC 启动及普通命令重启实测通过；[记录](verification/native-web-upgrade-board-20261015.md) |
| 中文管理 | 简体中文 LuCI、默认 root 空密码；官方无线表单和中文挂载页已验证；[UI 记录](verification/luci-ui-board-20261014.md) |
| 代理与工具 | Passwall 26.10.4、Xray 26.10.10、sing-box 1.14.3、unzip 6.0-r9；[双核心记录](verification/passwall-dual-core-20261013.md) |
| Docker | 29.6.1、Dockerman、Compose；ARMv7 小容器、资源限制、seccomp、DNS/物理网口 HTTP 已实测，持久数据和冷启动自启通过；[容器记录](verification/openwrt-system-board-20261014.md) |
| CPU / 内存 | 四核 `0-3` 在线，1 GiB 地址范围与 HIGHMEM；MemTotal 994384 kB，512 MiB 双模式及高于 768 MiB 的真实页测试通过；[记录](verification/production-profile-board-20261015.md) |
| 有线网络 | 100 Mbps 全双工、DHCP、双向 TCP、网线重连；统计语义和传输边界见[网口记录](verification/openwrt-ethernet-board-20261013.md) |
| 板载无线 | RDA5995 USB `1e04:8888`；WPA2 STA、AP 客户端、netifd 角色切换通过，默认关闭；最终模块复用早期 AP 客户端证据，见[无线记录](verification/rda-wireless-board-20261014.md) |
| USB 存储 | USB2 `320a:827b`、58.2 GiB；VFAT/NTFS3 只读文件访问和卸载通过，NTFS 访问前后写计数相同；[记录](verification/usb-storage-board-20261015.md) |
| SD / 磁盘管理 | 普通多块读写通过；中文 DiskMan、挂载点，SD FAT32/exFAT/ext4 格式化、挂载和读回通过，UUID 自动挂载跨普通重启保留；[记录](verification/production-profile-board-20261015.md) |
| time64 | 诊断及原生 musl 用户空间、选定应用 2040 年、NTP 2036/2038 边界在隔离 QEMU 通过；[应用说明](docs/openwrt-applications.md) |

## 当前限制

- SD/eMMC 继续使用已有 PIO、1-bit/25 MHz 控制器路径；DMA、宽总线和高速模式仍需驱动适配与硬件验证。历史单扇区首刷/升级耗时不代表新多块队列性能。
- eMMC 写入保留 p6/p9 边界；SD 原始擦除命令、锁卡、持久卡设置和未知命令仍被拒绝；普通文件系统格式化和读写已实测。热插拔、USB 写入速度尚未完整实测；自动挂载由用户配置。
- 无线仅一个 AP 或路由型 STA，2.4 GHz、HT20/legacy、开放或 WPA2-PSK/CCMP；
  不支持桥接 STA、mesh、WPA3 或 TKIP。无线 STA 上联旁路由组合未测。
- Docker 只验收小型 `linux/arm/v7` 工作负载；大容器、镜像仓库、IPv6 和综合性能未全部验收。
- 新打包的完整首刷包没有再次覆盖安装；复用已通过的首刷流程，改变的内核通过日常升级和 USB 访问验证。
- 原 Hinas 完整写回恢复没有重新进行破坏性实测；备份和恢复工具已有记录。
- 不宣称整机全部 Y2038 场景通过，也不将 QEMU 结果当作板载控制器的硬件验收。

## 当前包与 CI

2026.10.15.1 修复版的 sysupgrade 包 131,379,402 B，SHA-256：
`4b2c89e79ff70700100e1ae7d933b38632a709d792b6c7c764f3b46013bda218`。
内核 ABI `6.12.112~0757bd0e5fb295b399d4be7ea0c4decb-r1`。
配套首刷包和精确身份见[生产报告](verification/production-profile-board-20261015.md)。
含用户提供 RDA5995 固件的完整 Release 包按项目所有者授权公开；固件来源和哈希单独记录。

`2026.10.15` 因默认路径导致重复 radio 已撤回公开下载，旧文件身份仅供追溯。
替代版 [2026.10.15.1](https://github.com/UzkiS/ty1208z-kernel-port/releases/tag/v2026.10.15.1)
包括首刷包、sysupgrade、RAM 配套包、RDA5995 固件及两份清单；见[发布记录](verification/release-20261015.1.md)。
六个文件已正式公开，GitHub 大小/SHA-256 和公开清单下载核对通过；设备已安装无线修复，
真实 PHY hotplug 与普通重启后均只有一个 radio，见[修复报告](verification/rda-radio-path-20261015.md)。
普通 CI 附件只用于开发验证。

诊断 CI 在 `559c2d8` 上[通过](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38642766702)。
应用、router、eMMC、修复后 SD/router768 和 Docker/Passwall 组合已有成功干净构建；
实时结果与修复原因集中在 [CI 记录](verification/ci-closure-20261015.md)，不由工作流文件存在推断成功。
`8be787a` 诊断 CI 的旧只读 eMMC harness 因漏定义新的写入配置宏失败；已补齐并通过本地
ASan/UBSan，重跑与 Docker/Passwall/DiskMan 组合 CI 状态见上述记录。

安装只替换固定 p6/p9，保留 CA fastboot、持久 boot 环境、其他分区、
SD、boot0/boot1/RPMB 和安全状态。使用方法见[安装与升级](docs/installation-plan.md)。
