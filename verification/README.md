# 验证记录索引

当前可用功能、限制和包身份见 [STATUS](../STATUS.md)，使用方法见[安装与升级](../docs/installation-plan.md)。
本目录保存按日期、profile 和镜像区分的证据。早期报告的未完成项不自动延续为当前待办。
中文标题与下表提供导航；历史英文技术正文、命令、marker 和哈希保留原始证据含义。

## 安装与当前集成

- [三种网络固件 Release 文件与公开下载（2026-10-20）](release-20261020.md)
- [三种网络固件离线验证（2026-10-20）](network-variants-20261020.md)
- [固定 MAC 与默认桥接热点（2026-10-15）](stable-mac-bridge-20261015.md)
- [ext4 恢复默认实机验收（2026-10-15）](factory-reset-board-20261015.md)
- [ttyd 网页终端与 Compose 状态（2026-10-15）](ttyd-compose-board-20261015.md)
- [恢复默认按钮与路由修复（2026-10-15）](reset-ui-board-20261015.md)
- [.5 版恢复默认修复 Release 文件（2026-10-15）](release-20261015.5.md)
- [已撤回 .4 版 ttyd Release 文件身份（2026-10-15）](release-20261015.4.md)
- [已撤回 .3 版 Release 文件身份（2026-10-15）](release-20261015.3.md)
- [已撤回 .2 版 Release 文件身份（2026-10-15）](release-20261015.2.md)
- [无线重复 radio 修复（2026-10-15）](rda-radio-path-20261015.md)
- [已撤回 .1 版的 Release 文件身份（2026-10-15）](release-20261015.1.md)
- [已撤回原版 Release 的文件身份（2026-10-15）](release-20261015.md)
- [四核、全内存与磁盘管理实机验收（2026-10-15）](production-profile-board-20261015.md)
- [干净构建 CI 修复与结果（2026-10-15）](ci-closure-20261015.md)
- [紧凑 RAM 网页首刷实测（2026-10-14）](compact-first-install-board-20261014.md)
- [原生网页升级与持久根重启实测（2026-10-15）](native-web-upgrade-board-20261015.md)
- [系统集成交付阶段报告（2026-10-14）](progress-20261014.md)
- [USB 存储与 NTFS 实机验收（2026-10-15）](usb-storage-board-20261015.md)

## 硬件、启动与传输

| 记录 | 日期 |
|---|---|
| [原 Hinas 只读 SSH 基线](baseline-20261012.md) | 2026-10-12 |
| [CA 引导器受控检查](bootloader-inspection-20261012.md) | 2026-10-12 |
| [原生 RAM 系统命令重启实测](native-restart-board-20261013.md) | 2026-10-13 |
| [最小 Linux RAM 实机启动](ram-boot-20261012.md) | 2026-10-12 |
| [严格 SP805-ID 重启候选离线验证](restart-offline-20261012.md) | 2026-10-12 |
| [串口 CLI 离线验证](serial-cli-20261012.md) | 2026-10-12 |
| [串口传输中断与接收排查](serial-stream-20261013.md) | 2026-10-13 |
| [固定来源下载恢复](source-download-20261013.md) | 2026-10-13 |
| [临时 TFTP RAM 传输离线验证](tftp-ram-offline-20261013.md) | 2026-10-13 |
| [原 Hinas TTL 启动基线](ttl-boot-20261012.md) | 2026-10-12 |

## 内存、存储与 USB

| 记录 | 日期 |
|---|---|
| [eMMC 只读寄存器实测](emmc-audit-20261012.md) | 2026-10-12 |
| [eMMC 受限卡识别实测](emmc-identification-20261012.md) | 2026-10-12 |
| [eMMC 四个固定扇区读取](emmc-reads-20261012.md) | 2026-10-12 |
| [eMMC 用户区只读块实测](emmc-ro-board-20261014.md) | 2026-10-14 |
| [eMMC 只读诊断 CI](emmc-ro-ci-20261014.md) | 2026-10-14 |
| [eMMC 只读块源码与对象验证](emmc-ro-offline-20261014.md) | 2026-10-14 |
| [独立 eMMC 只读 RAM 候选](emmc-ro-ram-offline-20261014.md) | 2026-10-14 |
| [eMMC 单扇区写入与恢复实测](native-emmc-write-board-20261014.md) | 2026-10-14 |
| [原生 SD 非交互配置检查](native-sd-config-20261014.md) | 2026-10-14 |
| [原生只读 eMMC 与完整备份实测](openwrt-emmcro-board-20261014.md) | 2026-10-14 |
| [低768原生路由内存与应用实测](openwrt-router768-board-20261014.md) | 2026-10-14 |
| [原生只读 SD 路由系统实测](openwrt-sdro-board-20261014.md) | 2026-10-14 |
| [独立低768内存实测](ram768-board-20261014.md) | 2026-10-14 |
| [低768与 SD 诊断 CI](ram768-ci-20261014.md) | 2026-10-14 |
| [SD 无卡命令寄存器实测](sd-audit-board-20261013.md) | 2026-10-13 |
| [SD 卡识别与自动返回](sd-ident-board-20261013.md) | 2026-10-13 |
| [SD 只读块与 VFAT 实测](sd-ro-board-20261013.md) | 2026-10-13 |
| [SD 只读诊断干净 CI](sd-ro-ci-20261014.md) | 2026-10-14 |
| [USB host0 只读寄存器实测](usb-audit-board-20261013.md) | 2026-10-13 |
| [USB host0 只读审计离线验证](usb-audit-offline-20261012.md) | 2026-10-12 |
| [USB 时钟、能力与关闭实测](usb-clock-audit-board-20261013.md) | 2026-10-13 |
| [USB 时钟与能力候选离线验证](usb-clock-audit-offline-20261013.md) | 2026-10-13 |
| [USB host0 与 RDA 枚举实测](usb-host-board-20261013.md) | 2026-10-13 |
| [USB 时钟、PHY 与 HCD 编译](usb-host-compile-20261013.md) | 2026-10-13 |
| [USB host0 枚举镜像离线验证](usb-host-offline-20261013.md) | 2026-10-13 |

## 网口与应用

| 记录 | 日期 |
|---|---|
| [Xray 与时间探针干净 CI](applications-probe-clock-ci-20261013.md) | 2026-10-13 |
| [网口继承寄存器状态实测](ethernet-audit-20261012.md) | 2026-10-12 |
| [网口临时时钟与 PHY-ID 实测](ethernet-clock-id-20261012.md) | 2026-10-12 |
| [继承 PHY 的有线数据通路实测](ethernet-net-20261012.md) | 2026-10-12 |
| [独立有线 RAM 候选离线验证](ethernet-net-offline-20261012.md) | 2026-10-12 |
| [FEMAC 发送背压与统计修复](femac-xmit-20261013.md) | 2026-10-13 |
| [简体中文与空密码默认配置](luci-chinese-default-20261013.md) | 2026-10-13 |
| [原生应用 ARM QEMU 验收](openwrt-applications-20261012.md) | 2026-10-12 |
| [原生应用矩阵 CI 验收](openwrt-applications-ci-20261013.md) | 2026-10-13 |
| [独立应用外置 initrd RAM 打包](openwrt-apps-ram-offline-20261013.md) | 2026-10-13 |
| [隔离应用 DNS 切换验证](openwrt-dns-fixture-20261013.md) | 2026-10-13 |
| [原生网口 RAM 实测](openwrt-ethernet-board-20261013.md) | 2026-10-13 |
| [原生网口 RAM 离线验证](openwrt-ethernet-offline-20261012.md) | 2026-10-12 |
| [最小原生 OpenWrt 构建与 QEMU](openwrt-native-20261012.md) | 2026-10-12 |
| [NTP 客户端 2036 与 2038 边界验证](openwrt-ntp-time64-20261013.md) | 2026-10-13 |
| [原生路由应用与网口实测](openwrt-router-board-20261013.md) | 2026-10-13 |
| [原生应用与网口离线集成](openwrt-router-offline-20261013.md) | 2026-10-13 |
| [Passwall 双核心与 unzip 验收](passwall-dual-core-20261013.md) | 2026-10-13 |
| [双代理核心与 unzip 干净 CI](passwall-dual-core-ci-20261013.md) | 2026-10-13 |
| [原生板型与网口 probe 门禁](router-probe-guards-20261013.md) | 2026-10-13 |
| [时间同步前 Xray 启动检查](xray-browser-clock-20261013.md) | 2026-10-13 |

## 无线与系统

| 记录 | 日期 |
|---|---|
| [Docker、fw4 与 Passwall 组合 QEMU 验收](container-applications-qemu-20261014.md) | 2026-10-14 |
| [原生 Docker 软件包编译](container-packages-20261013.md) | 2026-10-13 |
| [原生 Docker 编译 CI 产物核验](container-packages-ci-20261013.md) | 2026-10-13 |
| [ARMv7 Docker 隔离 QEMU 运行](container-qemu-runtime-20261014.md) | 2026-10-14 |
| [中文 LuCI 页面渲染检查](luci-ui-board-20261014.md) | 2026-10-14 |
| [完整 RAM 系统与物理 Docker 实测](openwrt-system-board-20261014.md) | 2026-10-14 |
| [RDA 原生包 CI 产物核验](openwrt-wifi-ci-latest-20261013.md) | 2026-10-13 |
| [RDA 原生模块与 APK 验收](openwrt-wifi-package-20261013.md) | 2026-10-13 |
| [RDA 初始化补充源码审计](rda-startup-source-audit-20261013.md) | 2026-10-13 |
| [RDA 固定 USB 身份查询](rda-usb-identity-20261013.md) | 2026-10-13 |
| [RDA5995 STA、AP 与角色切换实测](rda-wireless-board-20261014.md) | 2026-10-14 |
| [RDA STA/AP 关联帧边界与所有权](wifi-association-frames-20261013.md) | 2026-10-13 |
| [RDA 芯片启动响应验证](wifi-chip-start-20261013.md) | 2026-10-13 |
| [RDA 控制响应回归](wifi-control-20261012.md) | 2026-10-12 |
| [RDA cfg80211 密钥回调回归](wifi-keys-20261013.md) | 2026-10-13 |
| [RDA USB Linux 6.12 模块移植](wifi-module-port-20261012.md) | 2026-10-12 |
| [RDA 不支持操作与 AP 停止顺序](wifi-operations-20261013.md) | 2026-10-13 |
| [RDA 定向扫描错误处理](wifi-scan-20261013.md) | 2026-10-13 |
| [RDA 扫描结果解析与所有权](wifi-scan-results-20261013.md) | 2026-10-13 |
| [RDA 接口启动失败回退](wifi-startup-20261013.md) | 2026-10-13 |

## 其他离线与 CI 记录

| 记录 | 日期 |
|---|---|
| [完整诊断 CI 验收](diagnostic-ci-20261013.md) | 2026-10-13 |
| [USB 与关联边界修复后的诊断 CI](diagnostic-ci-latest-20261013.md) | 2026-10-13 |
| [含 SD 只读审计的诊断 CI](diagnostic-sd-ci-20261013.md) | 2026-10-13 |
| [原生 sysupgrade 后端离线验证](native-web-upgrade-offline-20261014.md) | 2026-10-14 |
