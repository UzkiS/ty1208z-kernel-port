# 原生 OpenWrt 独立网口实验

`make openwrt-net TASKBASE=/absolute/linux/build-root` 在原生工具链完成后，
使用独立 `TASKBASE/ethernet/` 构建。`make openwrt-net-config` 只解析配置。
这是保留的低256、单核、UART/timer 网口 profile，当前系统状态另见[STATUS](../STATUS.md)。

身份为 `tianyi,ty1208z-ca-openwrt-net`，实际 UTS release 为 `6.12.112`。
构建和采集同时核对该 release、官方源码 revision、rootfs 与 DT 身份；
普通诊断不能借用该例外。驱动引用权威板级补丁，使用32位 DMA和专用 FESTAv220，
不导入独立 Linux 模块。

netifd 只提供 eth0 DHCP 客户端；包含 iperf3、ethtool、BusyBox ping/HTTP/netcat/hash，
没有 DHCP 服务、fw4、SSH、Wi-Fi、持久存储。仅从固定 packages 归档复制完整
iperf3 配方，保留许可与上游来源哈希，不依赖整个应用层。

构建检查选择、manifest、实际 DT/config、uImage CRC、解压范围及安装工具。
真实 datapath 函数运行 ASan/UBSan；QEMU 验证 procd/ubus/UCI、日志、time64 和
iperf3 回环，不附加 NIC，不模拟本机 MAC/PHY/DMA。

## 采集与证据

独立 RAM 输出为 `artifacts/openwrt-net1/`，无安装配方。
在完成精确 RAM 规划与启动后，使用实际串口名执行：

```text
python tools/openwrt_ethernet_board_cli.py --port SERIAL_PORT
python tools/openwrt_ethernet_board_cli.py --port SERIAL_PORT --iperf-start
python tools/openwrt_ethernet_board_cli.py --port SERIAL_PORT --iperf-collect
```

采集器拒绝 bootloader/Hinas/其他根身份，要求独立完成 marker，
iperf server 绑定 DHCP 地址、只接收一次测试并设60秒空闲超时。
原始 RX/TX 和元数据保留本地。

[实机记录](../verification/openwrt-ethernet-board-20261013.md)已通过 RAM 启动、
DHCP、双向 TCP 和网线重连；其中区分主机 WSL 时钟漂移和驱动 BUSY 计数语义。
[TX 修复记录](../verification/femac-xmit-20261013.md)补充真实函数的
ownership/retry/DMA 回归和后续集成结果。
物理流量与模拟吞吐不能互相替代。
