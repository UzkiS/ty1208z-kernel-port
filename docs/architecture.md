# 构建与集成边界

同一仓库保存共同板级依据，并不要求组件同时启用。目录只表示边界，
验收结果按内核、无线、系统集成分别记录。

| 层 | 本仓库内容 | 输入/依赖 | 独立验收 |
|---|---|---|---|
| Linux 板级支持 | `overlay/`、内核配置、Linux 补丁生成器 | 固定 Linux 源码、交叉工具链、板级事实 | 编译、内存临时启动、逐项外设测试 |
| 诊断环境 | `initramfs/`、BusyBox 配置、time64 probe | ARM 用户空间、现代内核系统调用 | QEMU 启动、shell、2040 年读写 |
| Wi-Fi，可选 | 目前为 `docs/wifi.md` 的驱动/固件清单 | 真实芯片 ID、USB 或 SDIO、相应内核驱动 | 扫描、联网、断线恢复；AP 模式单独验证 |
| OpenWrt/Kwrt 集成 | 目前为实施计划；尚未建立 target | 已验证内核版本/配置、匹配模块与用户空间 | 网络、防火墙、Passwall、DNS、性能与重启 |

Linux 诊断入口是 `make build`，不会引用 OpenWrt feeds、UCI 或无线配置。
之后 OpenWrt/Kwrt 集成应引用固定版本的内核补丁，不能修改上层服务时暗中
改变板级驱动。Wi-Fi 可关闭而不影响有线网络；未来可以在目标配置中选择它。

主线已有的无线驱动通过 Kconfig 选择，不再复制一份源码。只有确实需要外置
驱动时才另设包和版本锁定。其 `.ko` 仍需与目标内核 ABI 一致，这一依赖不会
因为拆分仓库而消失。与现有 Hinas 用户空间的兼容验证也是独立阶段。

## 源码与产物

- `config/sources.lock.json` 是下载版本、URL、哈希与已观察工具链的记录。
- `overlay/` 是新增 Linux 文件的唯一维护入口。
- `tools/make_kernel_patch.py` 从已校验的原版压缩包生成新增和修改文件的补丁。
- `tools/make_busybox_patch.py` 从原版 BusyBox 生成时间输出修复。
- `patches/` 提交可审查的生成结果；CI 再生成并要求 Git 无差异。
- `reference/` 提交来源清单，`reference/sdk/` 下载内容被忽略。
- `evidence/` 保留本地固件解析结果，避免把用户原固件内容发布到仓库。
- `.work/`、`artifacts/`、`logs/` 是可重新生成的本地文件。

不保存整个 Linux/OpenWrt 源码树，不引入 Git 子模块。需要贡献给上游时，
再建立对应 fork 和适合其审查规则的分支。
