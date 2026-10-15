# eMMC 存储与受限安装

当前系统已从eMMC ext4 rw根启动，p9在线扩展到6846 MiB，
配置及Docker数据跨断电保留。官方网页升级和普通命令重启已实测，
流程见[安装与升级](installation-plan.md)。

## 已测资源

`himciv200` / DesignWare MSHC位于 `0xf9830000`，GIC SPI35，
CRG40 `0xf8a220a0`。本机卡 `008G30`，用户区7,818,182,656 B。
VERID `0x5342270a`、HCON `0x00e44c81`、32位FIFO，
继承源100 MHz；SDK时钟源字段为bit9:8的75/100/50/15 MHz。
寄存器布局对应主线dw_mmc，不能由此推断DMA/高速或其他SoC时钟provider兼容。

分区布局见[硬件表](hardware.md)。安装只允许固定p6/p9，不修改
CA fastboot、持久环境、其他分区、boot0/boot1/RPMB或安全状态。
底层保持 PIO、单线、legacy 最高 25 MHz；生产队列支持正常多块数据传输，
擦除、boot/RPMB、分区切换和厂商命令仍被策略拒绝。
普通文件系统元数据写入的 `MMC_DATA_DAT_TAG` 软件提示已纳入生产策略，
所有写请求仍完整限制在 p6 或 p9；128 文件创建、改名、硬链接和删除负载已实测，
见[生产验证](../verification/production-profile-board-20261015.md)。

## 只读阶段与备份

| 入口 | 边界 |
|---|---|
| `make emmc-audit` | 只读固定controller/CRG配置，关闭MMC/BLOCK，不发卡命令 |
| `make emmc-ident` | 受限识别/EXT_CSD，关闭块设备；拒绝卡设置、写入/擦除和未知命令 |
| `make emmc-read` | 仅四个固定CMD17样本；Hinas kernel header和ext4 magic通过 |
| `make emmc-ro-compile` | 实际只读请求/块核心对象与回归，不输出启动镜像 |
| `make emmc-ro` | 独立低256只读块RAM系统，ext4 `ro,noload`、关闭与重启 |
| `make openwrt-router-emmcro` | 只读eMMC与网口、中文应用及内置重启的独立原生profile |

只读profile在硬件排队前限制请求，即使软件只读标志被清除仍拒绝写入。
主线控制器初始化会写controller状态并改变卡协议，
所以“存储只读”不等于“从不写任何MMIO”。
实机九分区、范围/重叠/末尾读、ext4文件访问、关闭和返回已通过；
[只读报告](../verification/emmc-ro-board-20261014.md)。

`tools/backup_emmc_readonly.py` 仅在精确原生只读系统核对FDT、身份、
九分区、只读和未挂载后，通过SSH读取完整用户区到电脑。
完整长度、传输退出和独立哈希通过后生成验收；
中断保留partial，不读取boot0/boot1/RPMB。
[原生报告](../verification/openwrt-emmcro-board-20261014.md)记录备份成功。
恢复用身份与完整备份保留在私有清单，公开说明不附原始内容。

## 持久系统

生产系统使用可写策略，普通只读 RAM 规划器仍只服务历史诊断 profile。
已完成单扇区写/读/恢复、紧凑首刷、完整读回、在线扩容和后续文件级升级，
见[首刷记录](../verification/compact-first-install-board-20261014.md)、
[升级记录](../verification/native-web-upgrade-board-20261015.md)。
完整原系统写回恢复未重复进行破坏性实测。

eMMC不宣告不支持的discard/WRITE_ZEROES，ext4使用普通写。
在线resize核对 `/dev/root` 指向p9，对挂载点执行扩容ioctl，
不放开raw mounted写入。重启时保留仍挂载的gendisk，
待host空闲后屏蔽IRQ并关闭PIO时钟。
SD 是另一控制器，生产配置独立启用普通多块读写；历史只读 profile 不随生产系统改变。
