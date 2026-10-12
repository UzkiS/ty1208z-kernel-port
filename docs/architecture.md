# 构建与集成边界

同一仓库保存共同板级依据，并不要求组件同时启用。目录只表示边界，
验收结果按内核、无线、系统集成分别记录。

| 层 | 本仓库内容 | 输入/依赖 | 独立验收 |
|---|---|---|---|
| Linux 板级支持 | `overlay/`、内核配置、Linux 补丁生成器 | 固定 Linux 源码、交叉工具链、板级事实 | 编译、内存临时启动、逐项外设测试 |
| 诊断环境 | `initramfs/`、BusyBox 配置、time64 probe | ARM 用户空间、现代内核系统调用 | QEMU 启动、shell、2040 年读写 |
| Wi-Fi，可选 | 独立来源锁、API 补丁、`wifi/overlay/`、`make wifi-usb-audit`/`make wifi-port` | 真实芯片 ID、独立配置下的目标内核、相应驱动/固件 | USB 对象和完整模块已本地编译；扫描、联网、AP 分别验收 |
| OpenWrt/Kwrt 集成 | 目前为实施计划；尚未建立 target | 已验证内核版本/配置、匹配模块与用户空间 | 网络、防火墙、Passwall、DNS、性能与重启 |

Linux 诊断入口是 `make build`，不会引用 OpenWrt feeds、UCI 或无线配置。
`make emmc-audit` 和 `make emmc-ident` 使用各自内核输出目录；前者只读寄存器且
关闭 MMC，后者通过受限 PIO 请求识别卡且关闭块设备。两者均不进入普通 diag1。
`make wifi-usb-audit` 使用单独的内核输出目录和配置，不改变诊断镜像；目前只编译
`wland_usb.o`，不链接模块、不加载固件。来源锁与适配范围见 [Wi-Fi 说明](wifi.md)。
`make wifi-port` 另行编译完整模块并执行制造入口/密钥回归；同样不改变诊断镜像，
不加载模块，不下载固件。无线新增 header 在 `wifi/overlay/`，与 Linux 板级文件分开。
之后 OpenWrt/Kwrt 集成应引用固定版本的内核补丁，不能修改上层服务时暗中
改变板级驱动。Wi-Fi 可关闭而不影响有线网络；未来可以在目标配置中选择它。

主线已有的无线驱动通过 Kconfig 选择，不再复制一份源码。只有确实需要外置
驱动时才另设包和版本锁定。其 `.ko` 仍需与目标内核 ABI 一致，这一依赖不会
因为拆分仓库而消失。与现有 Hinas 用户空间的兼容验证也是独立阶段。

原生 target 与 Passwall 集成边界见 [OpenWrt/Kwrt](openwrt.md)，网口主线复用与
内部 PHY/时钟待验证条件见 [Ethernet](ethernet.md)。这两层目前只有来源审计和
实施边界，没有可运行的 OpenWrt target 或新内核网口驱动验收结果。

## 源码与产物

- `config/sources.lock.json` 是下载版本、URL、哈希与已观察工具链的记录。
- `overlay/` 是新增 Linux 文件的唯一维护入口。
- `tools/make_kernel_patch.py` 从已校验的原版压缩包生成新增和修改文件的补丁。
- `tools/make_busybox_patch.py` 从原版 BusyBox 生成时间输出修复。
- `reference/wifi-rda-usb.lock.json` 固定可选 RDA 来源与逐文件哈希；下载器不下载固件。
- `tools/make_wifi_usb_patch.py` 生成单独的 USB API 审计补丁。
- `tools/make_wifi_port_patch.py` 从锁定来源生成完整模块补丁；无线新增文件在
  `wifi/overlay/`，现有控制协议函数的替换实现维护在 `wifi/replacements/`。
- `patches/` 提交可审查的生成结果；CI 再生成并要求 Git 无差异。
- `reference/` 提交来源清单，`reference/sdk/` 下载内容被忽略。
- `evidence/` 保留本地固件解析结果，避免把用户原固件内容发布到仓库。
- `.work/`、`artifacts/`、`logs/` 是可重新生成的本地文件。

不保存整个 Linux/OpenWrt 源码树，不引入 Git 子模块。需要贡献给上游时，
再建立对应 fork 和适合其审查规则的分支。
