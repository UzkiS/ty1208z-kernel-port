# 官方 OpenWrt 来源与集成

当前系统基于官方 `openwrt/openwrt` 的 `openwrt-25.12`，
固定提交 `58efa9917d4cc53fceed173529a286187649e827`，Linux 6.12.112。
中文 LuCI、Passwall 双核心、Docker、板载无线和 eMMC 安装已经整合；
当前结果见[状态页](../STATUS.md)。

## 固定来源

`openwrt/sources.lock.json` 固定基础源码归档；
`openwrt/applications/sources.lock.json` 固定 packages、LuCI、Passwall 与
Passwall packages 的完整归档、提交和 SHA-256。容器配方另有来源锁。
构建不执行上游定制脚本，不使用移动 feeds。

基础 Linux 压缩包 SHA-256 为
`164dc9d1f6c93c61a15e1f071c48379b467f2b17c469cce7223471968208ed03`。
OpenWrt 会继续叠加 generic 补丁并使用自己的配置和编译器；
相同基础版本并不意味着独立 Linux、Hinas 和 OpenWrt 的模块 ABI 相同。

最初的 `reference/openwrt-kwrt-audit.lock.json` 保留来源比较记录，Kwrt 不参与当前构建。
所审计的官方 target 没有 Hi3798MV100 专用板型；`armsr` 依赖 SystemReady/EFI，
不能替代本机 CA fastboot/uImage 加载路径。
CPU 使用 `cortex-a7` / `neon-vfpv4`，并不借用其他板型身份。

## 最小原生入口

```sh
make openwrt-config TASKBASE=/absolute/linux/build-root
make openwrt-toolchain TASKBASE=/absolute/linux/build-root
make openwrt-ram TASKBASE=/absolute/linux/build-root
```

使用普通 Linux 用户和 Linux 文件系统。`prepare_openwrt.py` 校验基础归档，
安装 `openwrt/overlay/target/linux/hi3798mv100`，引用权威板级补丁、
BusyBox stat time64 修复和 probe。原生 GCC 14.3.0 / musl 1.2.5 作为后续应用工具链。

这里的 `ram` 子目标仍是低256、单核、UART/timer 的独立最小 profile，
关闭 BLOCK/MMC/MTD/USB，仅回环网络，输出未实机验收的 initramfs uImage 与根归档。
它的限制不能套用到当前完整系统。镜像检查包括 CRC、DTB、加载地址和低16解压界限，
QEMU 使用实际原生用户空间检查 musl、UCI、procd/ubus、日志和 2040 年时间。

## 应用与完整系统

[应用构建](openwrt-applications.md)选择 Passwall 26.10.4、Xray 26.10.10、
sing-box 1.14.3、unzip 和中文界面，固定 Go 1.27.1 工具链配方。
其他代理核心和 geodata 不默认引入；支持的功能以实际选择和测试为准。

[网口集成](openwrt-router.md)在独立构建树加入测量过的 FEMAC/MDIO/PHY；
[无线包](openwrt-wifi.md)使用原生 Linux 6.12 cfg80211，避免混入 backports。
[完整系统](../openwrt/system/README.md)组合精确内核、APK、Docker 和无线，
并提供独立持久候选及安装打包流程。

编译检查、QEMU、CI 和实机结果分别记录。time64 的未来墙钟仅在隔离 QEMU 设置，
真实设备只作正常时间运行和 RAM 文件时间验证。
源码锁定与构建成功不能替代 p6/p9 备份、设备身份、恢复条件和精确包校验。
