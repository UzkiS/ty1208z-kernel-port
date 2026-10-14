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
| 内存 | 低 768 MiB 范围、约 744 MiB 可用；512 MiB 双模式压力和全部 PFN 边界通过；[原生记录](verification/openwrt-router768-board-20261014.md) |
| 有线网络 | 100 Mbps 全双工、DHCP、双向 TCP、网线重连；统计语义和传输边界见[网口记录](verification/openwrt-ethernet-board-20261013.md) |
| 板载无线 | RDA5995 USB `1e04:8888`；WPA2 STA、AP 客户端、netifd 角色切换通过，默认关闭；最终模块复用早期 AP 客户端证据，见[无线记录](verification/rda-wireless-board-20261014.md) |
| USB 存储 | USB2 `320a:827b`、58.2 GiB；VFAT/NTFS3 只读文件访问和卸载通过，NTFS 访问前后写计数相同；[记录](verification/usb-storage-board-20261015.md) |
| SD | 受限块读取及 VFAT 读取通过；驱动继续在请求层拒绝写入；[SD 记录](verification/openwrt-sdro-board-20261014.md) |
| time64 | 诊断及原生 musl 用户空间、选定应用 2040 年、NTP 2036/2038 边界在隔离 QEMU 通过；[应用说明](docs/openwrt-applications.md) |

## 当前限制

- 单核；上方 256 MiB 和低 16 MiB 保留，不能仅凭 DDR 容量放开内存。
- eMMC 单扇区 PIO；首刷 p9 写入约 29 分钟、读回约 11 分钟，后续网页升级的更新阶段约 16 分钟，上传另计。
- SD 只读；热插拔和其他文件系统没有完整实测。USB 写入、速度、exFAT 和外接 ext4 未新增实测，也未保存自动挂载配置。
- 无线仅一个 AP 或路由型 STA，2.4 GHz、HT20/legacy、开放或 WPA2-PSK/CCMP；
  不支持桥接 STA、mesh、WPA3 或 TKIP。无线 STA 上联旁路由组合未测。
- Docker 只验收小型 `linux/arm/v7` 工作负载；大容器、镜像仓库、IPv6 和综合性能未全部验收。
- 新打包的完整首刷包没有再次覆盖安装；复用已通过的首刷流程，改变的内核通过日常升级和 USB 访问验证。
- 原 Hinas 完整写回恢复没有重新进行破坏性实测；备份和恢复工具已有记录。
- 不宣称整机全部 Y2038 场景通过，也不将 QEMU 结果当作板载控制器的硬件验收。

## 当前包与 CI

最新私有 sysupgrade 包 131,399,882 B，SHA-256：
`38d42824f3189e24f079ec8693e334076736dce07fb8854c38e38079937544a2`。
内核 ABI `6.12.112~120d00c44db5befcdb6ed8d1f6825a56-r1`。
配套首刷包和精确身份见[USB 报告](verification/usb-storage-board-20261015.md)。
含原厂 RDA 固件的镜像仅私有交付。

诊断 CI 在 `559c2d8` 上[通过](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38642766702)。
应用矩阵和 Docker/Passwall 组合的最新干净构建仍待收尾；
实时结果与修复原因集中在 [CI 记录](verification/ci-closure-20261015.md)，不由工作流文件存在推断成功。

安装只替换固定 p6/p9，保留 CA fastboot、持久 boot 环境、其他分区、
SD、boot0/boot1/RPMB 和安全状态。使用方法见[安装与升级](docs/installation-plan.md)。
