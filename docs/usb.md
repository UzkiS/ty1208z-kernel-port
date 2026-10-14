# USB host0 与外接存储

当前系统已整合EHCI/OHCI host0、板载RDA无线和USB mass storage，
最新内核内置NTFS3。USB2 `320a:827b`、58.2 GiB设备已完成
VFAT与NTFS只读文件访问及卸载；NTFS读取前后写计数相同。
未进行USB写入/测速、格式化、修复或自动挂载配置，
见[存储实测](../verification/usb-storage-board-20261015.md)。

## 资源与来源

| 资源 | 地址/中断 |
|---|---|
| EHCI host0 | `0xf9890000/0x10000`，SPI66 |
| OHCI companion | `0xf9880000/0x10000`，SPI67 |
| CRG46 / CRG47 | `0xf8a220b8` / `0xf8a220bc` |
| USB0 / USB1控制 | `0xf8a20120` / `0xf8a20124` |
| SYSID0 | `0xf8000ee0`，本板 `0x37980100` |
| 板载无线 | bus1 port2，RDA `1e04:8888`，480 Mbps |

SDK固定 `07bug/HiSTBLinuxV100R005C00SPC060`
`a9f05973129d738e175416dd4a91b2c264ffcdd4`，文件身份见来源清单。
所参考clock/MV100文件保留Apache-2.0许可。
host0 tuning分支只需SYSID0低字节，不访问fuse。
host1不属于该适配范围。

## 时钟、PHY与所有权

独立实现按固定SDK顺序处理controller/UTMI/PHY reset、
interface、reference clock、PLL/test和共享时钟。
一个CCF provider供EHCI/OHCI共用，prepare/unprepare按引用计数管理，
避免仍有companion工作时关闭PHY。注册时不写控制寄存器，
last-user按SDK关闭；不会把易失模拟tuning恢复为继承值。

差分回归对全部256个低字节revision和8组初态，
逐项比较SDK原函数的写入/延时；实际helper及oracle运行ASan/UBSan。
无效SYSID不写；reset/readback失败报告错误，
不能把失败关闭报告为完成。源码与验证细节见
[编译报告](../verification/usb-host-compile-20261013.md)。

## 独立实验与结果

| 入口 | 范围与证据 |
|---|---|
| `make usb-audit` | 只读固定control/SYSID；状态未就绪时不读controller capability；[实机审计](../verification/usb-audit-board-20261013.md) |
| `make usb-clock-audit` | 精确初态下受限写时钟/PHY，读EHCI/OHCI能力并核对关闭；[实测](../verification/usb-clock-audit-board-20261013.md) |
| `make usb-host-compile` | 编译provider和主线HCD对象；无启动镜像 |
| `make usb-host` | 独立 `usb-host1` RAM枚举；关闭class/storage/network/firmware/PM/SMP等；[实机枚举](../verification/usb-host-board-20261013.md) |

独立host实验通过EHCI1.0、OHCI1.0、root hub、RDA高速枚举和共享时钟解绑/重绑。
`usb-diag` 只读取sysfs描述符，不代表固件或无线通过；
后续无线证据见[无线说明](wifi.md)。
低级审计、独立枚举和完整系统的存储权限分别由各profile控制。
QEMU只检查ARM shell及通用启动，不模拟真实USB/PHY。
