# 板载 SD/TF 卡槽

当前 OpenWrt 尚未启用 SD/TF 卡协议驱动，没有卡识别、读取或文件系统验收。
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

下一步依据本机测量建立受限卡识别与只读访问，并核对真实插卡情况。
文件系统、插拔和写入支持仍需后续实机验证。
