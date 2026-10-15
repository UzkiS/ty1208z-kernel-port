# 原生 OpenWrt RDA 模块与 APK

板载 RDA5995 的实际 STA/AP 集成已通过，见[无线说明](wifi.md)和
[无线报告](../verification/rda-wireless-board-20261014.md)。
本页说明保留的独立编译/打包入口，其产物本身不包含启动或安装镜像。

先执行 `make openwrt-toolchain`，再执行 `make openwrt-wifi-port`。
输出 `artifacts/openwrt-wifi-port/` 使用固定 GCC 14.3/musl、
固定 RDA 文件和与 `make wifi-port` 相同的生成补丁；
共享对象列表维护于 `wifi/Kbuild`。该入口从仓库内完整 RDA 树准备输入，
独立 kmod 只打包本次模块；固件由完整系统统一打包。

## cfg80211 与 ABI

固定 OpenWrt `kmod-cfg80211` 使用 backports 6.18.55，
而 RDA 适配针对原生 Linux 6.12 cfg80211。
独立内核选择 `CONFIG_CFG80211=y` 和 USB，明确排除 backports cfg80211/mac80211。
不得混用这两套栈，也不得复制独立 Linux 的模块。

检查器读取实际 UTS release、ABI hash、导出符号、
ARM ELF/vermagic/USB alias、APK 元数据和解包清单，
比较 strip 后的包内模块与本次真实模块。
包依赖精确 kernel/config ABI；独立编译包不含 firmware/autoload 或加载钩子。
解包检查不执行安装脚本。

回归拒绝错误内核版本/ABI、空 kmod、过期模块、未审查固件及自动激活。
独立 compile profile 关闭 host controller、存储、debugfs 和 SMP，
与完整系统的可启动无线 profile 分开。
早期 named-iovar 初始化阻碍是历史阶段，不能据此描述当前无线仍不可用。

最终系统使用匹配本次内核的 APK、仓库内匹配固件和 netifd/LuCI 适配。
运行固件随完整 Release 提供，完整上游驱动及固件参考已在本仓库维护，
详见 [RDA 本地维护](../wifi/vendor/README.md)。设备能力仍以实际响应和实测为准。
