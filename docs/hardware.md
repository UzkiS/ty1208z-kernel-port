# 板级证据与未知条件

设备：用户称为 TY1208Z 高安版。2026-10-12 已从正在运行的 Hinas 完成只读
SSH 采集；匿名化结果见 [基线记录](../verification/baseline-20261012.md)。
同日通过 CLI 接收了原系统的 TTL 启动输出，见
[引导记录](../verification/ttl-boot-20261012.md)。
Linux 报告的布局、引导器可用内存与高安校验状态是不同证据，不能相互替代。

## 本机运行时事实

| 项目 | SSH 测量 |
|---|---|
| 内核 / 用户空间 | `4.4.35_ecoo_81082668`；Ubuntu 24.04.4 LTS，32 位，glibc 2.39 |
| CPU | 四核 Cortex-A7，四核在线；采集时 1 GHz，cpufreq 报告最大 1.5 GHz |
| RAM | `/proc/iomem` 与运行 FDT 报告 `0x00000000–0x3fffffff`，1 GiB；MemTotal 737352 KiB |
| CMA / MMZ | CmaTotal 266240 KiB；启动参数 `mmz=ddr,0,0,256M`；两者不能直接视为安全保留区 |
| eMMC | `008G30`，7818182656 字节；`himciv200`，根分区为 p9 |
| SD/TF | 原 Hinas 已注册 `0xf9820000` 控制器/GIC 66，但当时未检测到卡；原生 RAM OpenWrt 临时模块只读测得 CRG39 `0x203`、VERID `0x5342270a`、CDETECT 零；卡协议/读取仍未验收，见 [SD/TF](sd.md) |
| 网口 | `hieth`，当前 100 Mbps 全双工；运行 FDT 和日志给出内部 PHY 地址 **1**，与离线参考的 2 不同 |
| Wi-Fi | USB `1e04:8888`，RDA Wlan，接口 FF/FF/FF；接口无驱动绑定，无无线网卡 |
| 时钟源 | `hisp804`；日志报告 24 MHz，运行 FDT 给出同样频率 |
| UART0 | 运行 FDT 给出 PL011 `0xf8b00000`、SPI 49、83.3 MHz 固定时钟；新内核已验证正式 PL011 双向交互，见下文 |

当前内核未暴露 `/proc/config.gz` 或对应 `/boot/config-*`。SSH 中的 dmesg
从部分早期内核信息开始，不含 bootloader 输出；后续 TTL 已补充引导阶段证据。

运行 FDT 的 reservation map 有五项：

| 起点 | 长度 |
|---|---|
| `0x3f87b000` | `0x00080000` |
| `0x3f878000` | `0x00002000` |
| `0x3f73e000` | `0x00003000` |
| `0x3ef54000` | `0x007e9000` |
| `0x3edbe000` | `0x00195000` |

这些项没有用途标签，可能含启动时分配；不能断言它们就是完整的安全内存范围。
诊断候选仍限制为低 256 MiB，避开原始引导日志中所有高位分配。

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
长 8935 字节。高安专用 fastboot 没有对应源码。当前 TTL 中引导器报告
`Secure boot is not enabled`，并实际接受现有 Hinas 的普通 legacy uImage；
新候选也已在同一引导器下通过普通 uImage 校验并从 RAM 启动；验证限于该镜像和本次路径。
另一个 Android 备份包含 ADVCA 头和 RSA 错误字符串，但 XML 留有 M301H 来源，
不能默认是当前机器的备份或据此判断当前验签状态。

## 本机引导阶段事实

当前引导器为 Fastboot `3.3.0-dirty`，2016-12-21 构建，CPU 标签为
`Hi3798Mv100 (CA)`，DDR Size 为 1GB。日志明确提供 `Press Ctrl+C to stop autoboot`，
首轮只接收；之后两次发送 Ctrl+C 均未进入引导器命令行，查询命令发送数为零。
之后用户更换 TTL 适配器，在 COM9 成功进入 `fastboot#`。CLI 接管已停下的
引导器，查询版本、帮助和环境均成功，无须再重启。已实测确认 `bootdelay=0`。
详见 [检查记录](../verification/bootloader-inspection-20261012.md)。

它从 eMMC 第 28672 块读取 40960 个 512 字节块，与 SSH 测得的内核分区对应。
当前镜像头在 `0x01ffffc0`，数据长 10862583 字节，加载和入口均为 `0x02000000`，
checksum 通过后启动 Linux 4.4。引导器打印 `Not hisilicon ADVCA image ...`。
随后实际 YMODEM/CRC/bootm 验证也确认诊断候选的镜像包装、附加 DTB 及加载路径可用。

引导器打印 11 项内存分配，详见引导记录；其 `Bound Addr: 0x8E62000` 的含义未确认。
已有五项 FDT reservation 只覆盖其中部分分配。实时 `getinfo ddrfree` 报告基址
`0x01000000`、长度 `0x3f000000`。SDK 参考实现按总 DDR 减固定下界计算该值，
不会扣除高位动态分配，因此仍须叠加原始分配记录判断位置。
`Secure boot is not enabled` 是本次引导器报告，并非独立读取 OTP/eFuse 得出的结论。

## 第一个候选的取舍

单 CPU 设备树和独立 MV100 定时器驱动使用原来的时钟源/CPU0 event 地址，
保留厂商的 event LOAD 双写处理。主线 `hisilicon,sp804` 是另一种 64 位寄存器
布局，未套用。没有复制厂商 SMP 电源启动或 CP15 初始化猜测。

DTB 的 RAM 限制为低 256 MiB，低 16 MiB 按实时 DDR free 下界保留，普通分配
从该界限之上开始。ARM 内核解压到 `0x00008000`；构建时验证压缩数据匹配 Image，
并核对 System.map 中映射后的 BSS 终点低于 16 MiB。传输采用原有镜像头地址
`0x01ffffc0`，payload/入口 `0x02000000`，与解压区、所有已观察高位分配不重叠。
没有导入旧 ATAG 内存和根设备参数；压缩入口采用附加 DTB。本次实机已确认
引导器接受、早期输出、正式 UART、IRQ/计时器和诊断 shell。
PL011 配置同时提供现代驱动需要的 `uartclk` 和 `apb_pclk`；频率与运行 FDT
相符。初版错误设置了 `arm,primecell-periphid = <0x001fe011>`，不匹配主线
PL011 的 AMBA ID，因此只有 earlycon 输出，/init 无法打开初始 console。
本机 Hinas FDT 没有该覆盖属性；移除后，主线从硬件读取 ID，成功绑定 PL011 rev2。
构建校验禁止再次加入这个 UART ID 覆盖。

实机 `diag` 记录：CPU0 timer GIC 硬件中断 58（SPI 26）、UART 硬件中断 81
（SPI 49），计时器计数在约一秒内增加 101，UART 输入/输出计数也增加，Err=0。
MemTotal 为 244480 KiB。2040 年 RAM 文件时间戳读回 `2208988800`，`time_t` 为
8 字节；没有更改本机墙钟。详见 [RAM 启动记录](../verification/ram-boot-20261012.md)。

## 后续外设与安装所需记录

1. 原 Hinas 正常启动的完整 TTL 日志；补足已取得 SSH 基线中的引导/早期信息。
2. 当前 bootloader 身份、可用命令、普通 uImage 和附加 DTB 启动已有实测记录。
3. 已测量分区布局对应的当前设备备份及恢复条件。
4. 可用 RAM、bootloader/安全区域和候选/解压镜像可能重叠的位置。
5. 已确认 RDA USB 身份对应的芯片版本、Wi-Fi 固件及电源/复位线索。

RAM 诊断已通过实测；外设、完整安全保留图、备份和恢复条件仍需各自验证。
尚未建立安装依据，也不提供刷写命令。
