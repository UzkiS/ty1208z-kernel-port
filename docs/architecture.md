# 构建与集成边界

当前集成系统已经完成 eMMC 安装；仓库同时保留各阶段独立 profile，便于定位与复现。
profile 的配置限制只约束该 profile，不能据此推断当前完整系统仍停留在早期诊断阶段。
实测状态见[状态页](../STATUS.md)，逐次证据见[验证索引](../verification/README.md)。

## 源码归属

| 层 | 维护入口 | 依赖与边界 |
|---|---|---|
| Linux 板级支持 | `overlay/`、`config/`、补丁生成器 | 固定 Linux 源码；新增文件以 overlay 为准，现有上游文件由检查锚点的生成器修改 |
| 诊断用户空间 | `initramfs/`、BusyBox 配置、time64 probe | 普通 Linux 诊断独立于 OpenWrt feeds |
| RDA 无线 | `wifi/vendor/`、`wifi/overlay/`、`wifi/replacements/`、`wifi/Kbuild` | 完整驱动与固件参考纳入本仓库；模块匹配实际内核 ABI |
| 官方 OpenWrt | `openwrt/` | 原生 GCC/musl、固定 feeds，引用同一份板级和 BusyBox 补丁 |
| 完整系统与安装 | `openwrt/system/`、`tools/build_native_system.py` 等 | 组合已验收组件，生成本机构建的 APK、模块和安装包 |

`config/sources.lock.json`、`openwrt/sources.lock.json` 和各层来源锁记录版本、URL 与哈希。
`tools/make_kernel_patch.py`、`tools/make_busybox_patch.py` 以及无线补丁生成器生成可审查结果；
`patches/` 不单独维护一份不同实现。厂商参考通过 `tools/fetch_references.py` 获取，
RDA 完整驱动与固件参考纳入 `wifi/vendor/`，默认从仓库内准备离线构建树；
运行所需的 USB 固件单独归档于 `firmware/rda5995/`。完整 SDK 和 Linux/OpenWrt
等大型上游源码仍通过来源锁获取，不提交重复副本。

## 构建入口

| 命令 | 产物范围 |
|---|---|
| `make build` / `make verify` | 最小单核、低256诊断；关闭存储与网络，不是完整系统 |
| `make emmc-audit` / `emmc-ident` / `emmc-read` / `emmc-ro` | eMMC 寄存器、识别、固定读取和只读块实验，依次独立 |
| `make sd-audit` / `sd-ident` / `sd-ro` | 独立 SD 控制器审计、识别和强制只读读取；生产系统另启用普通 SD 读写 |
| `make ethernet-audit` / `ethernet-clock-id` / `ethernet-net` | 网口寄存器、临时时钟/PHY-ID 和继承 PHY 状态的数据通路 |
| `make usb-audit` / `usb-clock-audit` / `usb-host` | USB 只读审计、时钟能力测量和 host0 枚举 |
| `make wifi-usb-audit` / `wifi-port` / `openwrt-wifi-port` | USB 单对象、完整模块和原生 APK 编译 |
| `make openwrt-ram` / `openwrt-net` | 原生最小 RAM 系统与独立网口系统 |
| `make openwrt-applications` / `openwrt-app-ram` / `openwrt-router` | 应用 QEMU、独立应用 RAM 包和应用/网口集成 |
| `make ram768` / `openwrt-router768` | 独立较大内存诊断与原生内存/网口集成 |
| `make openwrt-router-sdro` / `openwrt-router-emmcro` | 各自独立的只读 SD/eMMC 原生系统 |
| `make openwrt-container-packages` / `openwrt-container-qemu` / `openwrt-container-applications` | 容器编译、隔离运行与应用组合 QEMU 验证 |
| `make openwrt-system` | 组合四核/全内存、网口、可写存储、原生应用和 Docker 的生产 RAM 系统 |
| `make openwrt-first-install` | 使用预先准备的精确内核和根文件系统生成紧凑首刷包 |

多数原生命令使用 `TASKBASE=/absolute/linux/build-root`，并先完成 `make openwrt-toolchain`。
各入口的源码、配置、身份和输出目录相互隔离。完整系统与持久候选的后续打包参数见
[系统说明](../openwrt/system/README.md)。

## 验证与输出

独立 profile 保留自己的 DT、Kconfig、内核/rootfs 身份和检查结果。
RAM 规划器验证实测加载地址、解压范围与设备 CRC；低768 profile 还要求紧邻重启的
完整十一项 allocation 及新引导检查，不能由 `ddrfree` 推断安全内存。

QEMU 验证通用内核、原生服务、time64 与虚拟网络；控制器、PHY、固件和真实 RAM 边界
由实机报告证明。已经通过且未改变的组件复用既有证据，只检查改变的集成边界。

`.work/`、`artifacts/`、`reference/sdk/` 与本地证据不作为源码交付；
构建命令不自动连接设备。安装包、RAM 包和 QEMU 产物严格区分，不能互相替代。
