# 原生应用与网口 RAM 集成

这里说明独立 `router` 开发 profile；当前完整系统的持久安装与无线状态见
[STATUS](../STATUS.md)。

`make openwrt-router TASKBASE=/absolute/linux/build-root` 使用独立
`TASKBASE/router/`，复用固定原生编译器、应用 feeds 和板级补丁，
加入 FEMAC/MDIO/FESTAv220。输出中文 LuCI、Passwall 双核心、unzip、fw4、
dnsmasq-full、ip-full、ethtool 与 iperf3；模块匹配本次内核。

默认 `probe` 仅在 eth0 上作 DHCP 客户端，无 DHCP 服务接口；
接收 DHCP DNS，供解析器和 NTP 使用。root 默认空密码，恢复已有配置时保留已设置密码。
普通 router profile 关闭存储、USB、Wi-Fi 和 SMP，不能当作完整安装包。

## 已验收边界

[实机报告](../verification/openwrt-router-board-20261013.md)记录 RAM 启动、
有线 DHCP、中文 LuCI/Passwall、正常 DNS/NTP、双向 TCP 和代理测试；
TX 修复版本的新增错误/drop/FIFO 计数为零。
这些有限流量测试不代表路由或代理的最大吞吐。

QEMU fixture 在实际内核与根上运行 NTP/time64、DNS/TLS、认证和两种代理核心。
veth/network namespace 构成 client、router、origin，真实 netifd 建立路由，
fw4 产生转发规则。HTTPS 和 UDP 必须经过预期路径：
关闭直连转发时 HTTPS/UDP 控制连接失败；Passwall 启动 VLESS TLS、
TCP/UDP TPROXY 后成功，双向 UDP 各超过4096字节和10包，检查 nft 计数及表999；
停止代理后再次失败。512 MiB和240 MiB两次试验绑定同一套来源身份，
不向 guest 暴露磁盘或主机网络。

## RAM 输出与其他变体

`artifacts/openwrt-router1/` 含附加 DTB 的 uImage 和 `0x04000000` 独立 initrd。
打包器检查实际驱动 sanitizer、精确 board/clock/PHY 来源、应用证据与低16解压范围。
双设备 CRC、身份、资源或配置差异都会阻止启动。
`openwrt_ethernet_board_cli.py --profile router` 只采集精确 router 身份，
默认 `--profile net` 保持独立网口采集。

`openwrt-router768`、`openwrt-router-sdro`、
`openwrt-router-emmcro` 分别使用独立身份和构建树，
不改变普通 router 的权限。低768变体每次 RAM 启动需要新引导的完整 allocation。
只读 SD 第二轮最终关闭和返回已通过，见
[SD 报告](../verification/openwrt-sdro-board-20261014.md)；
eMMC 只读块、完整备份、关闭/返回见
[eMMC 报告](../verification/openwrt-emmcro-board-20261014.md)。

应用 CI 各矩阵任务从干净工具链构建；产物 `HARDWARE-UNTESTED` 标签不能由历史实测解除。
完整系统的构建、无线及安装后端见[系统说明](../openwrt/system/README.md)。
