# 三种网络固件离线验证

日期：2026-10-20。完整固件打包默认生成 `bridge`、`hybrid`、`nat`，
分别为原桥接、有线旁路由加无线 NAT、纯无线 NAT。网络行为和切换方式见
[版本说明](../docs/network-variants.md)。

## 构建与配置

共用 `.5` 对应的内核、RDA 模块、应用和安装器，未重编未变更内核或无线驱动。
三个离线根分别配置网络、无线、DHCP、防火墙和恢复默认快照；
`ty1208z-network` APK 登记固件默认类型，标记位于 `/usr/share/ty1208z-network/profile.json`。
该标记描述固件默认值，不能据此推断保留配置升级后的实际网络。

- 真实 ARM UCI 执行三种配置，并在隔离目录运行实际无线和 Docker 首次启动脚本。
  原桥接版的配置文件在生成阶段保持原字节；混合与 NAT 版的 Wi-Fi 属于独立 LAN，
  上联 `probe` 仍为 eth0 DHCP 客户端，只有无线 LAN 开 DHCP。
- 真实 ARM fw4/ucode 配合合成 netifd 状态生成两版规则，确认无线转发和 IPv4 masquerade。
  混合版有线入口允许同接口出口转发和管理，纯 NAT 版没有相应允许规则并拒绝上联管理。
  此过程只生成文本，不加载 nft 规则；主机 nft flowtable 状态不可用的提示不等于内核校验。
- 混合版 ttyd 由防火墙控制有线和无线入口；纯 NAT 版仍绑定下游 LAN。
  真实 UCI 回归覆盖此差异。
- 六个实际镜像生成完成。三个 sysupgrade 都通过实际归档、主机 sanitizer、ARM parser、
  暂存根逐文件读回及错误归档回归；三个首刷包通过实际 ARM outer/kernel/ext4 检查和 e2fsck。
- 三种升级根和首刷根均通过隔离恢复默认事务及真实 ARM UCI 测试。
  从实际首刷 ext4 读取 network、firewall、ttyd、类型标记及恢复默认快照，逐字节匹配暂存根；
  实际升级归档的网络、无线、防火墙、DHCP、ttyd 与类型标记也匹配暂存根。
- 预览下载集合包含 11 个文件：六个镜像、共用 RAM 包、固件归档、中文说明和两份清单。
  全部资产 SHA-256 与清单一致；RAM 包含三个类型各自的首刷清单，共用同一后端。

## 预览镜像身份

以下为本地 `2026.10.20-preview` 候选，不是已发布版本。
混合版因 ttyd 绑定修正重新生成，桥接和纯 NAT 复用未变更的已验证镜像。
所有 sysupgrade 为 131850442 B，所有 first-install 为 132823241 B。

| 类型 | 包 | SHA-256 |
|---|---|---|
| bridge | sysupgrade | `a0181fb3a77138cca4392f298ab9573b5efd0e4f1fa8d61fa0d75e12e84648bb` |
| bridge | first-install | `9c54b9251230df90adb7f2483ffd7a32db88b7caef73ec7598b4d0921c934eaa` |
| hybrid | sysupgrade | `23b01af908b21b98095fd455ce691676eba6e8e5d98aa10caf22ded41ed5c71b` |
| hybrid | first-install | `9db275e37b0db6db80d4cd832e453e577b69bf63eab0520a6a1a29f5ce4b240f` |
| nat | sysupgrade | `33bf3b34387b17c689fa636e5e01e017a329fbc73ea443e76aa647e84072235f` |
| nat | first-install | `1558d9ebf69824abc07de4670e64790b5b4f3763c6376289c5baa540d05ab6b7` |

内核 ABI 为 `6.12.112~0757bd0e5fb295b399d4be7ea0c4decb-r1`。
Ruff、ShellCheck、Python 语法与仓库 UTF-8/LF、只读固定 CI action 检查通过。

## 验证边界

本次没有连接或修改盒子，没有新增实机升级、重置、首刷、DHCP、同口转发、无线 NAT、
代理和吞吐验收。新完整构建脚本及手动 CI 工作流已加入仓库，但未在远端执行全新构建。
本地复用已构建的工具链、内核与应用，只重新打包改变的配置边界。
本离线记录完成时，公开稳定版本为 `2026.10.15.5`，未发布预览候选或撤下稳定版。
后续正式组装的 `2026.10.20` 六个镜像与上述哈希相同，正式文件名、发布状态和公开下载核对
见[三版发布记录](release-20261020.md)。
