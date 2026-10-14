# 板载 SD/TF

当前系统整合板载SD的受限只读块支持。
识别、块/重叠读、VFAT文件读取/卸载、控制器关闭和命令重启返回已实测，
[原生记录](../verification/openwrt-sdro-board-20261014.md)包含两轮最终结果。
SD写入不开放；热插拔、第二分区和其他文件系统没有完整验收。

## 资源与识别

控制器 `0xf9820000/0x1000`，SPI34（GIC66），
CRG39 `0xf8a2209c`，LDO `0xf8a2011c`。
实测CRG39 `0x203`、LDO `0x60`、DW版本 `0x270a`；
独立识别得到 `SU04G` SDHC，3,965,190,144 B，单线/25 MHz/legacy。
早期CDETECT零只是当时的信号观察，后来卡协议响应才建立识别证据。
eMMC的成功不能替代SD控制器验收。

## 构建阶段

- `make sd-audit`：只读固定CRG/LDO；时钟/复位满足条件才读controller配置，
  关闭MMC/BLOCK，不发卡命令。原生临时audit模块也要求精确router内核。
- `make sd-ident`：独立PIO识别，关闭BLOCK/MMC_BLOCK；
  允许原生识别、SCR/SSR与固定CMD6 CHECK，拒绝SET、ACMD6、写/擦和未知命令。
  继承CRG/LDO，主线会初始化controller，不能描述为只读MMIO审计。
- `make sd-ro`：独立只读块与文件系统候选，
  启用DOS/GPT、ext4/VFAT/exFAT；后两项中只有VFAT有本卡文件访问证据。
- `make openwrt-router-sdro`：独立 `router-sd` 树和板型身份，
  组合低768、网口及中文双核心应用。

## 请求保护与检查

`force_ro` 先于GPIO/WRTPRT返回只读，硬件队列前还核对卡类型、
扇区寻址、512字节容量、范围与请求sidecar。
读取只增加CMD17和最多8扇区的CMD18，后者需要精确只读CMD12 STOP。
CMD23、写、擦、SET、未知及越界请求仍拒绝。
清除块层只读标志不会绕过该保护。
块队列页大小是Linux注册要求，不代表写入或高速支持。

`sd-ro-probe` 只使用O_RDONLY，核对major/minor/容量/只读后验证读取及重叠；
`sd-ro-diag` 在RAM挂载点强制ro，ext4加 `noload`，读取有界且不输出文件名/内容，
随后卸载，不格式化或修复。实际policy/driver/get_ro运行ASan/UBSan；
QEMU不模拟板载SD。重启前要求无挂载并实际确认请求停止、IRQ与卡时钟关闭。
