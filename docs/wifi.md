# Wi-Fi 适配：本机为 RDA USB 方案

2026-10-12 的只读 SSH 基线确认机器存在 RDA USB 无线设备。当前 Hinas 没有
为它绑定驱动；现代内核也尚未集成对应驱动。Wi-Fi 仍是项目目标，扫描、联网
和 AP 模式需要分别验收。

## 本机已确认

| 项目 | 运行时测量 |
|---|---|
| USB ID / 产品 | `1e04:8888`；RDA Microelectronics / RDA Wlan |
| 位置与总线 | USB 1-2，高速 USB；接口 0 为 FF/FF/FF |
| 完整接口 alias | `usb:v1E04p8888d0000dc00dsc00dp00icFFiscFFipFFin00` |
| 驱动绑定 | USB 设备级有通用 usb 驱动；**无线接口没有驱动绑定** |
| 无线网卡 | 当前没有；`/proc/net/wireless` 为空 |
| SDIO | 本次 sysfs 未暴露 SDIO 设备 |
| 已安装模块 | RTL8188EU/FU alias 均不匹配；当前内核模块目录扫描未找到 RDA 模块 |

这是 RDA USB 家族的硬件依据；精确型号、修订版仍需驱动查询或芯片丝印确认。
不能只凭 USB ID 就断言一定是 RDA5995。USB 已枚举说明设备可见，不能证明
射频、固件下载或 USB 数据传输已经工作。日志还有 bulk 端点 maxpacket 64
告警，后续适配需要检查。

## 原固件与公开源码线索

来源未确证的 Android 备份含 `rdawfmac.ko`，USB alias 匹配 `1e04:8888`，
依赖 cfg80211，vermagic 为 **`3.10.0_s40 SMP mod_unload ARMv7 p2v8`**。
备份也有 rda5995 USB code/data 固件，包括 AP、P2P、RF 文件。模块与固件的
匹配关系、对本机的适用性及固件分发许可未确认；ID 匹配不能确证整份备份
属于本机。3.10 模块不能直接装到当前 4.4 或诊断 6.12 内核。

主线 Linux 6.12 无线目录中未找到匹配 RDA 驱动。固定海思 SDK 的 Wi-Fi drv
子树也未找到 RDA 路径。公开的 OrangePi RDA 内核提供了另一条源码线索：

- 仓库：[orangepi-xunlong/OrangePiRDA_kernel](https://github.com/orangepi-xunlong/OrangePiRDA_kernel)。
- 审计固定版本：`0844fd6fb5851d644b7af8380975f425c64428e6`。
- 路径：`drivers/net/wireless/rdaw80211`；Kconfig 声明 `rdawfmac.ko` 与 USB 选项，
  `wland_defs.h` 定义 VID `0x1e04`、PID `0x8888`，`wland_usb.c` 使用这组 ID。
- 同一 Kconfig 依赖该平台的 RDACBDEV/I2C 电源控制；源码仍使用旧 cfg80211
  调用形式及 `init_timer`。USB 路径还需要审查固件下载和芯片 ID 判断。

这只是有匹配 ID 的旧驱动参考，尚未证明能独立编译、驱动本机或移植到 6.12。
已检查文件的固定 URL/哈希见 [wifi-rda-audit.json](../reference/wifi-rda-audit.json)。
源码留在本地证据目录，不纳入最小诊断构建，也没有在盒子上加载旧模块。

## 后续实施顺序

1. 先让现代内核最小串口/计时诊断在实机启动，再适配 USB 控制器、PHY、时钟、
   复位和供电，确认现代内核也能稳定枚举这个设备。
2. 独立审计 RDA 源码、固件协议与许可，核对芯片版本。把平台电源依赖和 Android
   路径同 TY1208Z 板级支持分开，评估旧 cfg80211/定时器接口的移植成本。
3. 建立匹配目标内核的可选驱动构建；先验证 USB/固件初始化、扫描，再验证加密
   联网、DHCP、DNS、收发、断线重连与冷启动。AP 和 Passwall 路径单独验证。

找不到可用 RDA 驱动时，应报告具体阻碍并继续源码研究；不能把 Realtek 驱动
当成板载 Wi-Fi 的实现。内核版本升级本身不会补出 RDA 驱动。

## Realtek 离线线索与可选 USB 网卡

本地 Hinas 包及当前系统都有匹配旧 4.4 内核的 RTL8188EU/FU 模块；它们属于
其他 USB 设备，不对应本机板载 RDA。若以后另接支持的 USB 网卡，可单独评估：

| 设备 | USB ID | Linux 6.12 驱动 | 固件 |
|---|---|---|---|
| RTL8188EU | `0bda:8179`、`0bda:0179`、`07b8:8179` | rtl8xxxu / 8188e | `rtlwifi/rtl8188eufw.bin` |
| RTL8188FU | `0bda:f179`，厂商接口 | rtl8xxxu / 8188f | `rtlwifi/rtl8188fufw.bin` |

需核对完整接口描述。所查 8188f 子驱动声明 AP 支持，8188e 没有同样声明；
它们也要实机验收。更换网卡不是当前板载 RDA 适配的完成条件。
