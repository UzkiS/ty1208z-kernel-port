# 固定 MAC 与默认桥接热点实测（2026-10-15）

`2026.10.15.2` 修复重启改变 DHCP 身份的问题，并按默认使用要求启用无密码热点
`TY1208Z`。AP 与网口桥接，由主路由给盒子和无线客户端分配同网段地址；
管理使用主路由分给盒子的原地址，没有额外的 192 段管理子网。

## 原因与实现

旧 DT 没有 `mac-address` / `local-mac-address`，hisi-femac 启动日志报告随机地址，
`addr_assign_type=1`；UCI 只有 eth0 DHCP，未持久化地址。重启后主路由把它当成新设备。
`96-ty1208z-ethernet-mac` 在官方 boot S10 / netifd S20 之前保存本机 fallback MAC，
后续由 netifd 设置；用户已有 device/interface MAC 优先，公共镜像不含真实设备 MAC。

新的初始无线配置创建 `br-uplink`，包含 eth0 与 AP，桥显式沿用已保存网口 MAC；
`probe` 继续使用 DHCP。桥归 LAN 防火墙区，允许主路由 DHCP 与同网段管理，
没有在桥上运行 DHCP 服务器或为客户端做 NAT。Docker 保留独立区域，转发到 LAN。
保留配置升级时，已有 radio 的名称、密码、模式、关闭设置和网络布局不被覆盖。
默认开启适用于首次安装/恢复默认；本机原始未修改的关闭配置已按要求迁移。

## 实际检查

- 使用实际 ARM UCI 和合成 sysfs 验证首次保存、下一次随机 fallback 不覆盖、每设备地址不同、
  device/interface/旧 ifname 自定义地址保留、非法地址拒绝和幂等；测试纳入打包事务。
- 实际 ARM UCI 验证开放 AP、网口桥接、桥 MAC、LAN 防火墙归属、Docker 转发、
  保留自定义无线和 LAN，以及旧 eth0 路由配置继续进入 WAN 区。
- 使用真实 kernel APK 安装最终三个脚本，SHA-256 与最终 root 一致，APK 所有权可查询。
- 桥接配置完成两次普通命令重启；最后纳入 LAN 防火墙脚本的最终 APK 再重启一次。
  每次 boot_id 改变，原 SSH 主机密钥不变，MAC、DHCP 地址与已保存 network/wireless/dhcp 不变；
  eth0 `addr_assign_type=3`，桥地址与 eth0 一致，wlan0/eth0 同属 br-uplink。
  只有一个启用的 RDA radio，AP-ENABLED、wlan0 AP 与 TY1208Z/none 均通过。
- 通过桥内临时 veth / network namespace 客户端，真实主路由 DHCP 租约、盒子及主路由 ping 通过；
  管理入口可达并返回认证前 HTTP 403。另以已认证会话检查无线和 DiskMan 页面 HTTP 200。
  临时接口/命名空间已删除。这验证桥的 DHCP、过滤和管理路径，不替代真实无线客户端空口测试。
- 最终升级包通过主机 sanitizer/异常归档、实际 ARM parser 和实机 `sysupgrade --test`；
  本地 make lint 通过。未再次执行整个 sysupgrade 或完整 1 GiB 首刷。

相对 `.1` 的 root 逐文件比较，仅 `96-ty1208z-ethernet-mac`、`97-ty1208z-wireless`、
`98-ty1208z-docker-network` 和 `lib/apk/db/installed` 不同。Linux、RDA、固件与应用
运行字节相同，复用既有内存、存储、无线 STA/AP、容器及安装流程证据。
DHCP 的租约策略仍由主路由决定；需要永久固定 IP 时应在主路由保留租约。

## 私有证据身份

原始日志包含设备身份，留在公开 Git 之外。

| 记录 | SHA-256 |
|---|---|
| 旧随机地址诊断 | `ec998e74dd6a67fc2f698be00cfdb636b7695f71badcc1a77465d9615a222f44` |
| 最终 APK 安装及所有权 | `8e95e8f16b5228fe33aa9d9290866e6b8dcc619dfc0c7ca853ad9916389c2297` |
| 桥接两次普通重启 | `274345f27f9099ffa53647f477b402864cb1a0850aed742489fb461f20d7d119` |
| 最终 APK 普通重启 | `7a7e1fb043867a0bda4a5c059492c81a5cf51f31150ae3941af912e37ac2f044` |
| 桥内 DHCP 与管理访问 | `6cbffe460d169d1cb7eefba5fbaf40ae3bd249c1934cc25c0b97b009e5782cc1` |
| 最终升级包实机检查 | `f8a5c5a13ce03314ed1c935ef39065e9af72ca37bce8bf39071e808e48158db2` |
