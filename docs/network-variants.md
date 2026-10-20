# 三种网络固件

完整系统默认打包三种网络配置，共用同一份内核、驱动和应用。
文件名中的 `bridge`、`hybrid`、`nat` 用来选择首次安装或恢复默认时的网络行为。
`2026.10.20` 下载集合对应 [v2026.10.20 Release](https://github.com/UzkiS/ty1208z-kernel-port/releases/tag/v2026.10.20)。
三版已完成离线镜像与配置检查；混合版和 NAT 版尚未进行实机联网验收。

| 类型 | 有线接口 | Wi-Fi | 管理入口 |
|---|---|---|---|
| `bridge` 桥接版 | 主路由 DHCP 分配地址 | 与网口桥接，主路由分配地址 | 主路由给盒子分配的地址 |
| `hybrid` 混合版 | 主路由 DHCP 分配地址，可供同网段设备设置为网关 | 独立 `192.168.50.0/24`，盒子 DHCP 和 IPv4 NAT | 原有线地址或连接热点后访问 `192.168.50.1` |
| `nat` 路由版 | 作为 WAN，主路由 DHCP 分配地址 | 独立 `192.168.50.0/24`，盒子 DHCP 和 IPv4 NAT | 连接热点后访问 `192.168.50.1` |

三版默认开启 `TY1208Z` 开放热点，root 空密码。无线硬件仍为单个 2.4 GHz AP，
不增加 radio，不增加 WPA3。NAT 版默认不开放从上级有线网络访问管理服务，
也不提供同一有线接口进入、再转发给上级路由的旁路由功能。
混合版允许有线侧管理和同接口转发，并关闭 ICMP 重定向；出口伪装使回程经过盒子。
原桥接版保持既有默认配置，不自动改变主路由给客户端下发的网关。

## 如何选择和升级

`2026.10.20` 的六个镜像如下，按类型和安装方式选择一个：

| 类型 | 已安装系统的升级包 | 首次安装包 |
|---|---|---|
| 原桥接版 | `ty1208z-ca-bridge-sysupgrade-2026.10.20.bin` | `ty1208z-ca-bridge-first-install-2026.10.20.bin` |
| 有线旁路由加无线 NAT | `ty1208z-ca-hybrid-sysupgrade-2026.10.20.bin` | `ty1208z-ca-hybrid-first-install-2026.10.20.bin` |
| 纯无线 NAT 路由 | `ty1208z-ca-nat-sysupgrade-2026.10.20.bin` | `ty1208z-ca-nat-first-install-2026.10.20.bin` |

- 首次安装：选择对应类型的 `ty1208z-ca-<类型>-first-install-<版本>.bin`，
  配合该版本共用的 `install-ram` 包。临时 RAM 环境保持既有 DHCP 上联方式，
  持久启动后的网络由所选首刷包决定。
- 日常升级：选择 `ty1208z-ca-<类型>-sysupgrade-<版本>.bin`。
  勾选“保留配置”时，原网络、密码、无线名称及密钥继续保留，不会自动切换网络模式。
- 切换类型：备份所需配置后，不保留配置升级；或保留配置升级后使用“恢复默认设置”。
  恢复默认采用新固件对应类型的快照，同时清除密码和登录授权。
  NAT 版默认从 Wi-Fi 管理，切换前应具备无线连接条件。
- 从原桥接版切换到有线旁路由加无线 NAT，使用 `hybrid-sysupgrade`，在升级页取消“保留配置”。
  新默认值会清除管理密码及 SSH 登录授权，随后连接 `TY1208Z` 热点访问 `http://192.168.50.1/`，
  或使用主路由给盒子分配的有线地址管理。
- 下载后核对同一目录的 `SHA256SUMS.txt`。共用 RAM 包与固件归档只需下载一份；
  不要把 first-install 当作日常升级包。

## 地址、DNS 与访问范围

混合版作为有线设备网关时，应先在主路由为盒子保留 DHCP 地址，或手动设置合适的固定地址。
需要经过盒子的设备将 IPv4 网关设为盒子的有线地址；需要其 DNS 服务时同时设置 DNS。
原网络的 DHCP 仍由主路由负责，盒子只在独立无线子网提供 DHCP。

无线子网不能与主路由 LAN、VPN 或其他本地网段重叠；冲突时应修改 Wi-Fi LAN 地址及 DHCP。
混合版和 NAT 版的默认无线网络使用 IPv4；不默认提供 IPv6 RA、DHCPv6 或中继。
需要 IPv6 时另行配置上游前缀和转发策略。Passwall 的代理来源范围和 DNS 策略由用户配置，
NAT 本身不代表流量已经经过代理。

无线设备访问上级网络经过盒子 NAT，上级路由出公网还可能再做一次 NAT。
上级网络主动访问无线设备、跨网段投屏与自动发现需要额外路由、防火墙或发现服务配置。

## 开发者打包

从全新 Git 工作区开始，安装 Ubuntu 构建依赖后运行
`make openwrt-release-full VERSION=2026.10.20`；默认构建共用工具链、内核和应用，随后打包三版。
也可手动运行 GitHub Actions 的 `Three network firmware variants` 工作流，默认同样生成三版。
该工作流尚未在远端执行验收，CI 附件仍为开发候选，不代替正式 Release 下载。

在 Linux 文件系统中准备好同一内核的 disk root、RAM bootstrap 和原生构建树后执行：

```sh
make openwrt-release VERSION=2026.10.20 \
  TASKBASE=/absolute/build-root \
  NATIVE_SOURCE=/absolute/openwrt-source \
  DISK_ROOT=/absolute/clean-disk-root \
  BOOTSTRAP=/absolute/installation-ram \
  OUTPUT=/absolute/new-release-build
```

该入口默认依次生成三种升级包、三种首刷包、一个共用 RAM 包、一个固件归档、
中文说明和两份清单。已有完整产物不会被覆盖。网络配置在离线根中生成，再制作对应的
恢复默认快照；内核与主要应用只需构建一次。
`release/assets/` 为最终下载集合，`release-manifest.json` 记录各类型与文件的对应关系。
命令不会连接设备，也不会自动上传或公开 Release。现有单独打包入口继续默认 `bridge`，
`prepare_native_upgrade.py --network-profile hybrid|nat` 可单独生成其他类型。

三种固件的内核/模块 ABI、APK、异常归档和恢复默认仍分别校验。
离线配置和包检查通过不等于新组合已完成实机 DHCP、转发、NAT 或代理验收。
