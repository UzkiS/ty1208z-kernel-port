# Hi3798MV100 有线网络

Linux 6.12与原生OpenWrt已通过本板网口实测：
100 Mbps全双工、DHCP、双向TCP及网线断开/重连。
当前集成系统沿用该数据通路；历史状态和测量见
[物理网口记录](../verification/ethernet-net-20261012.md)、
[原生网口记录](../verification/openwrt-ethernet-board-20261013.md)。

## 资源与来源

| 资源 | 实测值 |
|---|---|
| Port0 MAC | `0xf9840000/0x400` |
| Global MAC | `0xf9841300/0x200` |
| MDIO | `0xf9841100/8` |
| 中断 | GIC SPI71 |
| 内部PHY | 地址1，ID `0x20669823`，FESTAv220 |
| 时钟控制 | CRG51 `0xf8a220cc`，继承值 `0x3`，启用后 `0xb` |
| PHY控制 | CRG `0xf8a22120`、选择 `0xf8a20008`、地址 `0xf8a20118`、LDO `0xf8a20844` |

固定SDK的hieth布局与主线 `hisi_femac.c`、`mdio-hisi-femac.c` 的
FIFO/队列、MDIO和全局寄存器对应，因此复用主线DMA mapping、NAPI和PHY框架。
SDK参考PHY地址2不适用于本机，实测地址1优先。
来源与逐文件哈希在 `reference/reference-manifest.json`。

## 板级适配

专用 `hisilicon,hi3798mv100-femac-inherited` 以32位DMA工作。
时钟provider核对精确继承状态，只开启CRG51 bit3并验证 `0xb`、等待5ms；
最后使用者释放时仅在仍为精确 `0xb` 时恢复 `0x3`。
不改PHY clock/reset/LDO/address或OTP寄存器，不宣称时钟频率测量。

专用FESTAv220先核对实际ID；MAC等待该驱动绑定，避免generic PHY soft-reset。
普通10/100协商会作正常易失PHY配置写入；
不复制厂商expanded fixup或MV200/MV300的OTP trim。
这仍是继承PHY状态的设计，完整独立PHY冷初始化没有另行建立。

MAC采用SDK双软件reset、little-endian、TX preamble和checksum设置，
不访问未确证的 `+0x340` coalescing，pause offload未启用。
RX-ready会弹出描述符，IRQ确认必须保留它到RX函数消费；
长度先验证再扣FCS或扩展skb。关闭时同步IRQ并先reset再unmap。
20ms TX回收monitor处理单向流量；TX-ready只在credit耗尽时武装，
NAPI只为pending RX继续循环，zero-budget只回收TX。

## 回归与实机边界

`tools/femac_patch.py` 维护检查式上游替换；
`tools/test_femac_datapath.py` 提取实际函数在ASan/UBSan下验证RX长度、
IRQ、预算、TX-only和monitor。旧版无限TX-only循环能够复现；
BUSY路径保留skb所有权，不再把正常背压计为drop/FIFO错误，
见[TX报告](../verification/femac-xmit-20261013.md)。

`make ethernet-audit` 仅观察继承寄存器；
`make ethernet-clock-id` 受限启用时钟、读PHY-ID并恢复；
`make ethernet-net` 才运行独立数据通路。
各profile具有独立身份和RAM门禁；QEMU不模拟MV100 MAC/PHY。
实际路由、Passwall与最大吞吐不能由PHY-ID或一次ping推断。
原生构建和采集见[独立网口说明](openwrt-ethernet.md)。
