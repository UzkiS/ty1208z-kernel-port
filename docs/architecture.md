# 构建与集成边界

原生应用与网口的独立集成入口为 `make openwrt-router`，它在自己的构建目录引用同一份
板级驱动、固定应用 feeds 和匹配模块；普通诊断、网口和纯应用镜像仍分别验收。
实际模拟转发/TCP TPROXY 与实机验收分别记录，见 [集成说明](openwrt-router.md)。

同一仓库保存共同板级依据，并不要求组件同时启用。目录只表示边界，
验收结果按内核、无线、系统集成分别记录。

| 层 | 本仓库内容 | 输入/依赖 | 独立验收 |
|---|---|---|---|
| Linux 板级支持 | `overlay/`、内核配置、Linux 补丁生成器 | 固定 Linux 源码、交叉工具链、板级事实 | 编译、内存临时启动、逐项外设测试 |
| 诊断环境 | `initramfs/`、BusyBox 配置、time64 probe | ARM 用户空间、现代内核系统调用 | QEMU 启动、shell、2040 年读写 |
| Wi-Fi，可选 | 独立来源锁、API 补丁、`wifi/overlay/`、`make wifi-usb-audit`/`make wifi-port` | 真实芯片 ID、独立配置下的目标内核、相应驱动/固件 | USB 对象和完整模块已本地编译；扫描、联网、AP 分别验收 |
| 官方 OpenWrt 集成 | `openwrt/` 独立 RAM target、来源锁及原生构建入口 | 板级补丁、原生工具链/用户空间、固定应用 feeds | 原生镜像、QEMU time64、网络、防火墙、Passwall、DNS 与性能 |

Linux 诊断入口是 `make build`，不会引用 OpenWrt feeds、UCI 或无线配置。
`make ram768` 单独构建低 768 MiB 内存压力测试及已测 MV100 重启门禁；
启动前必须核对本次引导器的完整分配表，见 [内存实验](ram.md)。
`make sd-audit` 单独观察板载 TF 控制器与 CRG39/LDO，关闭 MMC/BLOCK；
它与 eMMC 的识别、读取候选分开验收，见 [SD/TF](sd.md)。
`make emmc-audit` 和 `make emmc-ident` 使用各自内核输出目录；前者只读寄存器且
关闭 MMC，后者通过受限 PIO 请求识别卡且关闭块设备。两者均不进入普通 diag1。
`make emmc-ro-compile` 单独编译用户区只读块支持和实际请求/块核心回归；
它不输出镜像。`make emmc-ro` 另建低256 RAM-root 镜像，只有精确用户区只读、
已测分区、ext4 ro,noload 与独立 shutdown/restart 配置可通过 RAM 规划器；
编译/模拟已通过，尚无实机块/文件系统/重启验收，详见 [eMMC](emmc.md)。
`make ethernet-audit` 另用独立配置/输出目录，只观察固定时钟/复位状态，并在
继承状态符合条件时通过 MDIO 读取 PHY ID；关闭 NET、debugfs 和存储，不进入普通诊断。
`make ethernet-clock-id` 单独验证暂时启用已实测的 MAC 时钟位、读取 PHY ID 并恢复；
它有自己的设备树、配置、身份和验收，不属于只读寄存器观察，也不启动网口 DMA。
`make usb-audit` 单独只读观察 host0 时钟/PHY 控制和 SYSID0；仅在继承状态符合
来源条件时读取 EHCI/OHCI capability，不启用 USB 栈、不进行设备事务或控制写入。
它有独立配置、产物和验收，见 [USB](usb.md)。
`make restart` 单独验证 SP805 显式系统重启；启动时仅检查真实硬件 ID/禁用状态，
仅在系统重启回调中写复位寄存器，不提供看门狗服务。严格 SP805 ID 候选仍未通过
本机验证；原生 router 的精确临时模块已通过命令重启及自动重新加载 RAM 系统，
见 [restart](restart.md)。SD 只读临时模块也能在该 router 中测量并卸载，
无需切换镜像。
`make sd-ident` 的独立 PIO/metadata/restart 候选已识别本机 SDHC，
并通过命令重启自动返回；当前原生 router 的 MMC/BLOCK 仍关闭，
生产系统的块设备/文件系统整合尚未完成。
`make sd-ro` 在独立身份下启用块设备和受限只读文件系统；队列门禁继续拒绝卡
写入。本机已完成块读取及 VFAT 文件读取/卸载，并自动返回原生 router。
`make openwrt-router-sdro` 是另一个显式原生 SD/较大内存入口；它复用同一受限
SD 策略，并在独立构建树中整合中文应用和网卡。实际配置依赖、镜像校验及
新引导器分配证据单独检查，普通 router 仍关闭存储；
[实机边界](../verification/openwrt-sdro-board-20261014.md)。
`make wifi-usb-audit` 使用单独的内核输出目录和配置，不改变诊断镜像；目前只编译
`wland_usb.o`，不链接模块、不加载固件。来源锁与适配范围见 [Wi-Fi 说明](wifi.md)。
`make wifi-port` 另行编译完整模块并执行制造入口/密钥回归；同样不改变诊断镜像，
不加载模块，不下载固件。无线新增 header 在 `wifi/overlay/`，与 Linux 板级文件分开。
之后 OpenWrt 集成应引用固定版本的内核补丁，不能修改上层服务时暗中
改变板级驱动。Wi-Fi 可关闭而不影响有线网络；未来可以在目标配置中选择它。

主线已有的无线驱动通过 Kconfig 选择，不再复制一份源码。只有确实需要外置
驱动时才另设包和版本锁定。其 `.ko` 仍需与目标内核 ABI 一致，这一依赖不会
因为拆分仓库而消失。与现有 Hinas 用户空间的兼容验证也是独立阶段。

原生 target 与 Passwall 集成边界见 [OpenWrt/Kwrt](openwrt.md)，网口主线复用与
内部 PHY/时钟待验证条件见 [Ethernet](ethernet.md)。原生 RAM target 已通过配置解析、
OpenWrt 通用补丁叠加、完整原生 GCC/musl 镜像构建及核心用户空间 QEMU time64。
新内核的基本网口收发已有[实机验收](../verification/ethernet-net-20261012.md)，
原生 OpenWrt 的独立网口镜像也已完成 RAM 启动、DHCP、双向 TCP 和网线重连；
时钟与驱动计数的实测边界见[实机记录](../verification/openwrt-ethernet-board-20261013.md)。
完整路由、无线和持久安装仍需分别验证。

## 源码与产物

`make ethernet-net` 是独立的有线网口 RAM 实验入口：启用上游 FEMAC/MDIO、
专用 MV100 初始化和保留状态的 FESTAv220 驱动，但关闭存储、USB、模块与 SMP。
它有独立设备树、配置、BusyBox 网络工具、构建目录和 RAM 启动校验，不会改变
默认诊断镜像或 OpenWrt 应用构建。完整 PHY 冷启动和实机收发按网口验收单独记录。


- `config/sources.lock.json` 是下载版本、URL、哈希与已观察工具链的记录。
- `openwrt/` 维护原生集成；引用板级及 BusyBox time64 补丁，不复制驱动源码。
- `overlay/` 是新增 Linux 文件的唯一维护入口。
- `tools/make_kernel_patch.py` 从已校验的原版压缩包生成新增和修改文件的补丁。
- `tools/make_busybox_patch.py` 从原版 BusyBox 生成时间输出修复。
- `reference/wifi-rda-usb.lock.json` 固定可选 RDA 来源与逐文件哈希；下载器不下载固件。
- `wifi/Kbuild` 维护共享模块对象列表；`openwrt/wifi-port/` 只负责独立原生
  OpenWrt 编译/打包入口，引用同一来源锁和生成补丁，不与普通诊断/路由镜像
  同时启用。它使用原生 Linux 6.12 cfg80211，并排除 OpenWrt backports；
  目标内核 ABI、实际 APK 与实机无线分别验收，见 [说明](openwrt-wifi.md)。
- `tools/make_wifi_usb_patch.py` 生成单独的 USB API 审计补丁。
- `tools/make_wifi_port_patch.py` 从锁定来源生成完整模块补丁；无线新增文件在
  `wifi/overlay/`，现有控制协议函数的替换实现维护在 `wifi/replacements/`。
- `patches/` 提交可审查的生成结果；CI 再生成并要求 Git 无差异。
- `reference/` 提交来源清单，`reference/sdk/` 下载内容被忽略。
- `evidence/` 保留本地固件解析结果，避免把用户原固件内容发布到仓库。
- `.work/`、`artifacts/`、`logs/` 是可重新生成的本地文件。

不保存整个 Linux/OpenWrt 源码树，不引入 Git 子模块。需要贡献给上游时，
再建立对应 fork 和适合其审查规则的分支。
