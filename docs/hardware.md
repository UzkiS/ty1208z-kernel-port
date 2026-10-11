# 板级证据与未知条件

设备：用户称为 TY1208Z 高安版；当前关机。所有地址取自本地 Hinas 内核
附带 DTB 和固定厂商源码，尚非本机运行时测量。

| 项目 | 离线依据 |
|---|---|
| SoC / CPU | `hi3798mv100-series`；四个 Cortex-A7 节点 |
| UART0 | `0xf8b00000`，GIC SPI 49，PL011，参考时钟 83.3 MHz |
| GIC | distributor `0xf8a01000`；CPU interface `0xf8a02000` |
| 定时器 | 24 MHz；原时钟源 `0xf8a29000`，CPU0 event `0xf8a2a000`，SPI 26 |
| eMMC | `0xf9830000`，厂商 himciv200 控制器 |
| Ethernet | `0xf9840000`，hieth，参考 PHY 地址 2 |
| 参考 RAM 基址 | `0x00000000`；实际容量和可用/安全保留范围未知 |
| 参考内核分区 | 14 MiB 起、20 MiB 长；实际当前布局待确认 |
| 参考 Hinas 根分区 | `/dev/mmcblk0p9`，610 MiB 起；不能据此直接生成写入命令 |

原内核是 `4.4.35_ecoo_81082668`。源码参考 SDK 不等于该内核的完整、准确
可重现源码；本阶段完成源码对照，没有宣称重建了现有 Hinas 内核。

## 原始文件身份

| 文件 | SHA-256 |
|---|---|
| 已知刷入成功的高安 `fastboot.bin` | `f891870ec98b4df48de879afc1e1973cf14cc9057eb18a5a41d974fab3e935bc` |
| 本地 Hinas 内核 | `baaa86b45dc9f10ac9611695c1f37311ac6eda6315fd03e5fb2c8cf7f92afaf5` |
| 通用包 fastboot，不能替换上述引导 | `3bded87f15c1ebd686f39c23570650ac2b53a97815b592a0130b06fe2ce954ae` |

Hinas uImage CRC 正常，加载/入口 `0x02000000`，DTB 位于文件偏移 10853712、
长 8935 字节。高安专用 fastboot 没有对应源码，刷入成功并不证明关闭了安全启动。
另一个 Android 备份包含 ADVCA 头和 RSA 错误字符串，但 XML 留有 M301H 来源，
不能默认是当前机器的备份或据此判断当前验签状态。

## 第一个候选的取舍

单 CPU 设备树和独立 MV100 定时器驱动使用原来的时钟源/CPU0 event 地址，
保留厂商的 event LOAD 双写处理。主线 `hisilicon,sp804` 是另一种 64 位寄存器
布局，未套用。没有复制厂商 SMP 电源启动或 CP15 初始化猜测。

DTB 的 RAM 为待校正的 256 MiB，不能称为安全范围。没有导入旧 ATAG 内存和
根设备参数。若当前引导直接传入另一 DTB，或安全保留与此冲突，必须先修改方案。
PL011 配置同时提供现代驱动需要的 `uartclk` 和 `apb_pclk`；频率仍待实机确认。

## 进入实机阶段所需记录

1. 原 Hinas 正常启动的完整 TTL 日志、内核版本、CPU、内存和保留区域。
2. 当前 bootloader 身份、可用命令和已成功镜像的加载方式。
3. 真实分区布局、当前设备备份及恢复条件。
4. 可用 RAM、bootloader/安全区域和候选/解压镜像可能重叠的位置。
5. USB/SDIO 设备 ID、Wi-Fi 电源/复位线索及已加载模块。

这些记录完成前，只交付离线候选，不提供假定可用的刷机或临时启动命令。
