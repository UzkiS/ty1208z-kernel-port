# 当前状态与验收边界

更新于 2026-10-20。当前交付已完成 TY1208Z CA 实机 eMMC 安装和原生网页升级。
本页只记录当前集成状态；独立实验的当时结论见[历史验证索引](verification/README.md)。

## 已完成

| 项目 | 当前结果与证据 |
|---|---|
| 系统来源 | 官方 OpenWrt 25.12 固定 `58efa9917d4cc53fceed173529a286187649e827`，Linux 6.12.112；固定版本构建，不持续追踪 master |
| 三种网络固件 | `2026.10.20` 已公开 bridge、hybrid、nat 各自首刷/升级包，共 11 个下载资产；真实 ARM UCI/fw4 和对应重置快照检查通过。新混合/NAT 组合未实机联网验收；[离线记录](verification/network-variants-20261020.md)、[发布记录](verification/release-20261020.md) |
| 首次安装 | TTL/TFTP 启动专用 RAM 环境，官方中文 LuCI 首刷；1 GiB p9 和 p6 完整读回，eMMC ext4 rw 根启动；[记录](verification/compact-first-install-board-20261014.md) |
| 容量与持久化 | p9 在线扩至 6846 MiB，文件系统约 6.5 GiB；配置和容器内容跨断电保留；[安装说明](docs/installation-plan.md) |
| 恢复默认 | LuCI“系统 → 恢复默认设置”、firstboot/factoryreset 支持 ext4 配置重置；清登录授权/密码，保留 MAC、SD、Docker/用户数据，实际重置和后续重启通过；[后端记录](verification/factory-reset-board-20261015.md)。`.5` 修复按钮灰色并改为 `system/reset`，真实 DOM、实机页面/预检通过；[页面记录](verification/reset-ui-board-20261015.md) |
| 后续升级与重启 | 官方 LuCI 保留配置升级、stage2 RAM pivot、文件级根更新、p6 读回、默认 eMMC 启动及普通命令重启实测通过；[记录](verification/native-web-upgrade-board-20261015.md) |
| 中文管理 | 简体中文 LuCI、默认 root 空密码；官方无线表单和中文挂载页已验证；[UI 记录](verification/luci-ui-board-20261014.md) |
| 代理与工具 | Passwall 26.10.4、Xray 26.10.10、sing-box 1.14.3、unzip 6.0-r9；[双核心记录](verification/passwall-dual-core-20261013.md) |
| Docker | 29.6.1、Dockerman、Compose；ARMv7 小容器、资源限制、seccomp、DNS/物理网口 HTTP 已实测，持久数据和冷启动自启通过；[容器记录](verification/openwrt-system-board-20261014.md) |
| 网页终端 / Compose 界面 | `.4` 首刷、升级和配套 RAM 包已包含官方 ttyd LuCI 插件及中文翻译，实机终端/配置页及 WebSocket 登录执行命令通过。Compose v5.1.4 命令可用，Dockerman 无 Compose 项目页；[记录](verification/ttyd-compose-board-20261015.md) |
| CPU / 内存 | 四核 `0-3` 在线，1 GiB 地址范围与 HIGHMEM；MemTotal 994384 kB，512 MiB 双模式及高于 768 MiB 的真实页测试通过；[记录](verification/production-profile-board-20261015.md) |
| 有线网络 | 100 Mbps 全双工、DHCP、双向 TCP、网线重连；统计语义和传输边界见[网口记录](verification/openwrt-ethernet-board-20261013.md) |
| 板载无线 | RDA5995 USB `1e04:8888`；WPA2 STA、AP 客户端、netifd 角色切换通过，默认开启 TY1208Z 开放热点并与网口桥接；最终模块复用早期 AP 客户端证据，见[无线记录](verification/rda-wireless-board-20261014.md) |
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

当前正式版本为 [2026.10.20](https://github.com/UzkiS/ty1208z-kernel-port/releases/tag/v2026.10.20)。
三种 sysupgrade 均为 131,850,442 B，三种 first-install 均为 132,823,241 B；
各版哈希、共用 RAM 包和其他资产身份见[发布记录](verification/release-20261020.md)。
内核 ABI `6.12.112~0757bd0e5fb295b399d4be7ea0c4decb-r1`。
完整 Release 包含项目所有者授权公开的 RDA5995 固件。

`2026.10.15` 因重复 radio、`.1` 因随机网口 MAC、`.2` 因缺少 ext4 恢复默认入口、`.3` 因缺少 ttyd LuCI 页、`.4` 因恢复默认按钮灰色撤回公开下载，旧文件身份仅供追溯。
原桥接 [2026.10.15.5](https://github.com/UzkiS/ty1208z-kernel-port/releases/tag/v2026.10.15.5)
继续保留下载；见[历史发布记录](verification/release-20261015.5.md)。
新版本 11 个资产已正式公开，服务器大小/SHA-256、匿名说明及清单下载和公开标签均匹配。
切换网络类型需取消“保留配置”或升级后恢复默认；新混合/NAT 版没有新增实机联网验收。
本机 MAC 和桥地址已持久化，桥接多次普通重启保持原 DHCP 地址；单个 TY1208Z 开放热点自启，
原桥接模式的主路由 DHCP 和管理路径通过，见[修复记录](verification/stable-mac-bridge-20261015.md)。
普通 CI 附件只用于开发验证。

诊断 CI 在 `559c2d8` 上[通过](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38642766702)。
应用、router、eMMC、修复后 SD/router768 和 Docker/Passwall 组合已有成功干净构建；
实时结果与修复原因集中在 [CI 记录](verification/ci-closure-20261015.md)，不由工作流文件存在推断成功。
`8be787a` 诊断 CI 的旧只读 eMMC harness 因漏定义新的写入配置宏失败；已补齐并通过本地
ASan/UBSan。组合 CI 随后因 staged host 工具 PATH 自循环失败，构建入口已修复并用实际
OpenWrt prerequisite 复现/回归；重跑状态见上述记录，未把运行中或局部回归当作整套通过。

安装只替换固定 p6/p9，保留 CA fastboot、持久 boot 环境、其他分区、
SD、boot0/boot1/RPMB 和安全状态。使用方法见[安装与升级](docs/installation-plan.md)。
