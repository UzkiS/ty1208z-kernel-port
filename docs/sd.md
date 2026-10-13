# 板载 SD/TF 卡槽

独立 RAM 候选已实机识别 SDHC 卡，并可通过命令重启自动返回中文 OpenWrt。
独立强制只读候选也已完成块读取及 VFAT 文件读取；当前原生 OpenWrt 尚未整合
SD/TF 块设备，其他文件系统、插拔和生产系统整合仍需验收。
eMMC 的实机识别与四扇区读取不能代替 TF 卡槽验收；两者使用不同控制器。
2026-10-13 已在原生中文 RAM 路由系统中完成临时模块只读寄存器测量，
见 [实机记录](../verification/sd-audit-board-20261013.md)。

原 Hinas 的只读基线中，`0xf9820000` 的 SD 控制器已占用 MMIO 并注册 GIC
硬件中断 66，但日志明确显示 `eMMC/MMC/SD Device NOT detected!`。这是当时
未检测到卡的记录，不能证明卡槽正常，也不能据此断言当时没有插卡。

| 项目 | 来源依据 |
|---|---|
| 控制器 | 原系统资源和固定 SDK：`0xf9820000`，长度 `0x1000` |
| 中断 | 原系统 GIC 66；SDK SPI 34 |
| 时钟 | SDK CRG39，`0xf8a2209c`；源频率选择与 eMMC CRG40 相同 |
| 供电控制 | 原固件/SDK DT：LDO `0xf8a2011c`，shift 0 |
| 插卡/写保护 | SDK 控制器寄存器 CDETECT `0x50`、WRTPRT `0x54` |

`make sd-audit` 生成独立 `sd-audit1` RAM 候选。它只观察固定 CRG39/LDO，
仅当 SDK 定义的时钟使能位 0/1 有效且复位位 4 清除时读取控制器的身份、
总线/FIFO 配置和插卡/写保护寄存器；否则跳过控制器 MMIO。
它不启用 MMC/BLOCK，不读取 FIFO/中断状态，不发送卡命令，不写控制寄存器
或卡数据。实际 probe 的资源、映射失败、128 组时钟/复位组合和 MMIO 读序
通过 sanitizer 检查；实际 DT/config、RAM 布局和 QEMU 结果分别验收。

`tools/build_openwrt_sd_audit_module.py` 可以对已完成的原生 router 构建临时模块。
它与 restart 模块共享精确内核构建器：检查实际 router DT/config、zImage、
符号和原生编译器/libc；模块编译也拒绝 BLOCK/MMC。模块仅允许原生 RAM router
身份，为同一只读 probe 注册三个固定资源；失败的 probe 会撤销设备/驱动注册，
卸载释放全部资源。它不修改运行 DT，也不需要切换 RAM 镜像。
实际独立/原生 probe 和注册、失败回退、移除路径均通过 ASan/UBSan。

实机测得 CRG39 `0x00000203`（来源时钟 50 MHz）、LDO `0x00000060`，
控制器版本低 16 位 `0x270a`；CDETECT/WRTPRT 都是零。
CDETECT bit0 低按控制器定义表示有卡信号，但当前插卡情况未由用户确认，
且 CLKENA 为零、没有发过卡协议命令，不能据此认定卡存在或卡槽正常。
临时模块测量后已卸载；中文路由与 restart 模块继续运行，IRQ Err 为零。

后续仍需建立扇区和文件系统只读访问；插拔和写入支持分别验收。

## 受限 SD 卡识别与自动返回

独立入口 `make sd-ident` 使用实测控制器 `0xf9820000`、CRG39 `0x203`、
LDO `0x60`、DW VERID/HCON 和 GIC 66；不符则在主线驱动写 MMIO 前拒绝。
SDK 的 LDO mask 为 `0x70`，`0x60` 对应 3.3 V bypass/enable；候选继承这个值，
不调用 CRG/LDO/provider 或进行电压切换。主线 DW 控制器初始化会写本控制器
的复位、IRQ/FIFO、分频/时钟和电源位，受限识别请求会改变卡协议状态，
所以这个阶段不是只读寄存器观察。

请求在 DW 排队前过滤：允许 SD 原生识别、8 字节 SCR、64 字节 SSR 和固定
CMD6 CHECK 查询；拒绝 CMD6 SET、ACMD6、数据写入、擦除、扇区读写和未知请求。
主机强制 PIO、单线、legacy、最高 25 MHz，排除 MMC/SDIO、高速和供电序列模块。
BLOCK/MMC_BLOCK 关闭，没有块设备或挂载入口。扩展寄存器发现被禁用，防止
内核尝试启用 SD 缓存/电源设置。容量属性只输出已经解码的非唯一字段。

2026-10-13 该候选已在本机识别 `SU04G` SDHC，容量 `3965190144` 字节，
与单线/25 MHz/legacy 状态一起通过串口门禁；IRQ Err 为零。
卡槽目前有可响应的卡，不再只依赖 CDETECT 信号。该结果仍未建立扇区、文件
读取或插拔支持。见 [卡识别实机记录](../verification/sd-ident-board-20261013.md)。

该独立镜像还内置原生路由已实测的窄范围 MV100 显式 restart helper，
并要求其专用 DT 身份。启动仅验证 SYSID0/零 ID cells/禁用 watchdog 状态。
重启前 DW remove 停止 rescan/请求、屏蔽 IRQ、关卡时钟，再读回确认。
`board_restart_cli.py --profile sd-ident1` 验证设备树、实际绑定、注册和实际
shutdown 标记，不自动重试 reset。实机命令重启、CA 引导检查和自动返回中文
OpenWrt 已完成，不需要人工断电。

## 强制只读块设备与文件系统候选

`make sd-ro` 构建独立 `sd-ro1`，专用身份为 `tianyi,ty1208z-ca-sd-ro-ram`。
它沿用实测 SD 控制器、CRG39/LDO、PIO、单线/25 MHz 和 restart/shutdown，
启用 MMC_BLOCK、DOS/GPT 分区及 ext4、VFAT、exFAT；原生 router 仍单独构建。

DW 的 `force_ro` 在读取 GPIO/WRTPRT 前返回只读，但保护不限于这个标志。
实际驱动验证已识别的 SD 卡、扇区寻址及 512 字节扇区容量；队列门禁只增加
范围内 CMD17 和最多 8 扇区的 CMD18，后者必须附带准确的只读 CMD12 STOP。
单独的只读错误恢复 STOP 也受参数/flags 检查。CMD23、写入、擦除、CMD6 SET、
未知请求、越界、多余 sidecar 和超过一页的数据均拒绝，尚未进入硬件队列。
即使用户清除块设备的只读标志，该请求门禁仍有效。SDHC/SDXC 之外的扇区
读取被拒绝；不进行 SDSC 块长设置或任何电压/高速/缓存切换。

Linux 6.12 的块队列要求 `max_hw_sectors >= PAGE_SECTORS`；沿用 metadata-only
主机的单扇区上限会使队列注册失败。此候选设置 8 扇区/4096 字节上限，
允许相应的受限多块读取，保留原识别候选的单块/无 BLOCK 配置。

`sd-ro-probe` 只用 `O_RDONLY` 和 BLKROGET/BLKGETSIZE64 查询；确认块设备 major、
minor、只读和容量后读取首页及跨页重叠区，并比较重叠内容。它不输出用户数据。
`sd-ro-diag` 只把识别出的文件系统挂载到 RAM `/tmp`，强制 `ro`；ext4 另外
使用 `noload` 禁止日志回放。文件读取有数量/深度上限，不跟随符号链接，不输出
文件名或内容，随后卸载。禁止修复、格式化和物理写入探测。

实际 policy/driver/队列和 `get_ro` 回调通过 ASan/UBSan；包括所有 opcode/方向、
末尾扇区、flags/STOP 变异、缺失/非 SD 卡和 GPIO/WRTPRT 覆盖。DT/config、
RAM/CRC、串口 PTY 和 QEMU 分别检查。物理结果需以该镜像的独立实机记录为准；
QEMU 不模拟板载 SD 控制器。该镜像已完成本机只读块、VFAT 挂载/文件读取/卸载
及自动返回，见 [实机报告](../verification/sd-ro-board-20261013.md)。第二分区的
文件系统尚未识别，ext4/exFAT 仍只有编译结果。插拔、生产 router 整合和写入
支持仍需后续验收。
