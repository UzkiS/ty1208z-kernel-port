# eMMC：先识别控制器，再启用存储

当前 Hinas 实测控制器为 `himciv200`，MMIO `0xf9830000`、GIC SPI 35；
运行 FDT 的 clock specifier 为 160（0xa0），时钟控制器基址 `0xf8a22000`。
eMMC 型号 `008G30`，容量 7818182656 字节。分区布局已记录，尚无完整备份。

固定 SDK 中 `himciv200_def.h` 的寄存器布局对应 DesignWare MSHC：
CTRL/PWREN/CLKDIV/CMD/RESP、VERID/HCON 和 IDMAC 地址均有对应主线定义。
这是复用 `dw_mmc` 的依据，尚不能证明所有版本特性、FIFO/IDMAC 与时序兼容。
SDK CRG40 的源频率字段是位 9:8：75/100/50/15 MHz；enable 实现还改变
时钟门控、相位和复位，因此不能把其他海思型号的 clock driver 直接套到 MV100。
固定源码及哈希见 [SDK 来源清单](../reference/reference-manifest.json)。

## 独立寄存器诊断

`make emmc-audit` 在独立内核输出目录生成 `artifacts/emmc-audit1/`。
它复用已验证的 RAM initramfs、串口、GIC、单 CPU timer 和内存限制；
普通 diag1 不启用这个审计驱动，也没有审计节点。

审计驱动只有固定资源和只读白名单：

| 资源 | 读取内容 |
|---|---|
| eMMC 0xf9830000 | CLKDIV、CLKSRC、CLKENA、CTYPE、FIFOTH、USRID、VERID、HCON |
| CRG40 0xf8a220a0 | 当前值；按固定 SDK 字段推导源频率 |

它不读取 FIFO 或中断状态，不写寄存器，不改变时钟/复位，不发 MMC 命令。
Kconfig 要求 MMC 和 BLOCK 均关闭，固定资源不符则拒绝探测。
这些读取只描述 bootloader 留下的状态，不建立可读卡、更不建立可写卡的结论。
构建、镜像布局、DT 资源、QEMU RAM 用户空间必须通过后才能实机启动；
QEMU 不模拟这些 MV100 寄存器。

实机仍使用已测量的 YMODEM → device CRC → bootm RAM 路径；
诊断采集使用 `board_diag_cli.py --profile emmc-audit1`，核对相应 kernel release
和 `EMMC_AUDIT_READ_ONLY_COMPLETE`。具体换镜像需先安排从当前 RAM 系统
回到引导器；不得把已经重启过的 RAM 当作保留了此前镜像。

## 后续驱动阶段

2026-10-12 独立审计已在本机通过，实测 VERID=`0x5342270a`、HCON=`0x00e44c81`、
FIFOTH=`0x207f0080`、CRG40=`0x00040103`。低 16 位版本为 DW `0x270a`，
HCON 的 FIFO 接口为 32 位；当前源频率为 100 MHz，CLKDIV=1 对应 50 MHz 卡时钟，
CTYPE 表示继承的 8 位总线。具体镜像、日志身份和限制见
[实机审计记录](../verification/emmc-audit-20261012.md)。尚未在新内核枚举卡或读取扇区。

下一候选评估复用主线 DesignWare，先继承实测 CRG/pinmux 状态，限制为 PIO、单线、
最高 25 MHz，并在硬件排队之前限制 MMC 请求。CMD6 卡设置修改、数据写入、擦除、
安全/未知命令均拒绝；关闭 BLOCK/MMC_BLOCK，不提供原始块访问。
首个卡访问候选只做识别和 EXT_CSD 读取，禁用高速/电压切换；
不挂载原 Hinas，先对照型号、容量和固定范围读取的结果。
完整 Hinas 启动还依赖分区解析、ext4、用户空间及模块兼容；安装前另行建立备份和恢复路径。
