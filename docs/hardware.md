# 板级证据与未知条件

设备：用户称为 TY1208Z 高安版。2026-10-12 已从正在运行的 Hinas 完成只读
SSH 采集；匿名化结果见 [基线记录](../verification/baseline-20261012.md)。
Linux 报告的布局、引导器可用内存与高安校验状态是不同证据，不能相互替代。

## 本机运行时事实

| 项目 | SSH 测量 |
|---|---|
| 内核 / 用户空间 | `4.4.35_ecoo_81082668`；Ubuntu 24.04.4 LTS，32 位，glibc 2.39 |
| CPU | 四核 Cortex-A7，四核在线；采集时 1 GHz，cpufreq 报告最大 1.5 GHz |
| RAM | `/proc/iomem` 与运行 FDT 报告 `0x00000000–0x3fffffff`，1 GiB；MemTotal 737352 KiB |
| CMA / MMZ | CmaTotal 266240 KiB；启动参数 `mmz=ddr,0,0,256M`；两者不能直接视为安全保留区 |
| eMMC | `008G30`，7818182656 字节；`himciv200`，根分区为 p9 |
| 网口 | `hieth`，当前 100 Mbps 全双工；运行 FDT 和日志给出内部 PHY 地址 **1**，与离线参考的 2 不同 |
| Wi-Fi | USB `1e04:8888`，RDA Wlan，接口 FF/FF/FF；接口无驱动绑定，无无线网卡 |
| 时钟源 | `hisp804`；日志报告 24 MHz，运行 FDT 给出同样频率 |
| UART0 | 运行 FDT 给出 PL011 `0xf8b00000`、SPI 49、83.3 MHz 固定时钟；尚未以 TTL 验证新内核输出 |

当前内核未暴露 `/proc/config.gz` 或对应 `/boot/config-*`。SSH 中的 dmesg
从部分早期内核信息开始，不含 bootloader 输出，不能代替完整 TTL 启动日志。

运行 FDT 的 reservation map 有五项：

| 起点 | 长度 |
|---|---|
| `0x3f87b000` | `0x00080000` |
| `0x3f878000` | `0x00002000` |
| `0x3f73e000` | `0x00003000` |
| `0x3ef54000` | `0x007e9000` |
| `0x3edbe000` | `0x00195000` |

这些项没有用途标签，可能含启动时分配；不能断言它们就是完整的安全内存范围。
暂不扩大诊断候选的 RAM，也不据此生成 RAM 加载命令。

当前分区通过 `blkdevparts` 提供；起点/长度已按 sysfs 的 512 字节扇区核对：

| 设备 | 名称 | 起点 MiB | 长度 MiB |
|---|---|---:|---:|
| p1 | boot | 0 | 1 |
| p2 | bootargs | 1 | 1 |
| p3 | baseparam | 2 | 4 |
| p4 | pqparam | 6 | 4 |
| p5 | logo | 10 | 4 |
| p6 | kernel | 14 | 20 |
| p7 | busybox | 34 | 64 |
| p8 | backup | 98 | 512 |
| p9 | ubuntu | 610 | 6846 |

另有各 4 MiB 的 eMMC boot0、boot1 和 RPMB。以上是识别结果，没有读取分区镜像、
确认备份或提供写入命令。

## 离线参考

| 项目 | 离线依据 |
|---|---|
| SoC / CPU | `hi3798mv100-series`；四个 Cortex-A7 节点 |
| UART0 | `0xf8b00000`，GIC SPI 49，PL011，参考时钟 83.3 MHz |
| GIC | distributor `0xf8a01000`；CPU interface `0xf8a02000` |
| 定时器 | 24 MHz；原时钟源 `0xf8a29000`，CPU0 event `0xf8a2a000`，SPI 26 |
| eMMC | `0xf9830000`，厂商 himciv200 控制器 |
| Ethernet | `0xf9840000`，hieth，参考 PHY 地址 2 |
| 参考 RAM 基址 | `0x00000000`；本机容量见上表，可用/安全范围仍待引导阶段核实 |
| 参考内核分区 | 14 MiB 起、20 MiB 长；与本机 SSH 布局一致 |
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
PL011 配置同时提供现代驱动需要的 `uartclk` 和 `apb_pclk`；频率与运行 FDT
相符，新驱动仍待实机串口确认。

## 进入实机阶段所需记录

1. 原 Hinas 正常启动的完整 TTL 日志；补足已取得 SSH 基线中的引导/早期信息。
2. 当前 bootloader 身份、可用命令和已成功镜像的加载方式。
3. 已测量分区布局对应的当前设备备份及恢复条件。
4. 可用 RAM、bootloader/安全区域和候选/解压镜像可能重叠的位置。
5. 已确认 RDA USB 身份对应的芯片版本、Wi-Fi 固件及电源/复位线索。

这些记录完成前，只交付离线候选，不提供假定可用的刷机或临时启动命令。
