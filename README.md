# 天邑 TY1208Z CA：Linux 与 OpenWrt 适配

[![诊断 CI](https://github.com/UzkiS/ty1208z-kernel-port/actions/workflows/diagnostic.yml/badge.svg)](https://github.com/UzkiS/ty1208z-kernel-port/actions/workflows/diagnostic.yml)

本仓库为天邑 TY1208Z 高安版 / Hi3798MV100 提供 Linux 6.12 板级支持和基于官方
OpenWrt 25.12 的系统集成。**已完成实机 eMMC 安装、中文 LuCI 网页升级和普通命令重启**。
当前能力、证据和限制见 [STATUS.md](STATUS.md)，操作流程见[安装与升级](docs/installation-plan.md)。

## 当前系统

- 官方 OpenWrt 固定提交 `58efa9917d4cc53fceed173529a286187649e827`，Linux 6.12.112。
- 支持 LuCI“系统 → 恢复默认设置”，清除配置/密码/授权，保留本机 MAC、SD、Docker 和用户数据；[说明](docs/factory-reset.md)。
- 简体中文 LuCI；默认账号 `root`、空密码；升级可保留已有配置和密码。
- Passwall 26.10.4，含 Xray 26.10.10、sing-box 1.14.3；InfoZIP unzip。
- Docker 29.6.1、中文 Dockerman、Compose；eMMC 数据持久化和冷启动自启已实测。
- 中文 ttyd 网页终端及配置页，入口为“服务 → 终端”，使用系统账号与密码。
- 有线 DHCP、双向 TCP；板载 RDA5995 的 WPA2 STA/AP 已分别实测，默认开启无密码热点 `TY1208Z`，与网口桥接，由主路由分配地址。
- eMMC ext4 可写根和完整 p9 在线扩容；USB 存储的 VFAT/NTFS3 文件访问已实测（写入仍需用户自行挂载验证）。
- 中文 DiskMan 磁盘管理和挂载点；SD 的 FAT32、exFAT、ext4 格式化、挂载、读写及重启自动挂载已实测。

生产配置已解除单核、低 768 MiB 和单扇区队列限制，启用四核 SMP、HIGHMEM、
完整 1 GiB 地址范围及 SD/eMMC 多块读写；四核、994384 kB MemTotal、512 MiB 高位页测试和持久启动已实测。
引导器实际占用按精确地址保留，早期只读诊断 profile 继续用于回归。无线 STA 上联组合旁路由、STA/AP 同时工作、
USB 写入及吞吐没有新增验收。time64 已覆盖选定用户空间与应用的 QEMU 案例，
不代表所有软件或整机未来时钟行为全部验证。

## 安装与使用

正式下载：[2026.10.15.4 Release](https://github.com/UzkiS/ty1208z-kernel-port/releases/tag/v2026.10.15.4)。
首刷、日常升级、RAM 配套包、无线固件和校验文件在同一页面，RAM 包内附独立中文步骤。
`2026.10.15` 的重复 radio、`.1` 的随机 MAC、`.2` 缺少 ext4 恢复默认、`.3` 缺少 ttyd LuCI 页的问题已修复，受影响旧版均撤下公开下载。
连接热点后使用主路由分给盒子的地址管理；不另设无线子网，不在桥上运行 DHCP 服务器。

首次安装采用 TTL 加网线启动专用临时 OpenWrt，再通过官方 LuCI“系统 → 备份与更新”
上传 first-install 包；已安装的系统使用独立 sysupgrade 包。两种包不能互换。
首刷只替换已核对的 p6/p9，沿用现有 CA fastboot 和持久启动环境。
已知可用的[高安 fastboot 原始文件](bootloader/ty1208z-ca/README.md)另行归档，正常升级无需重刷。

镜像包含经项目所有者授权的 RDA 固件，公开 Release 与 `firmware/rda5995/` 一并提供哈希清单。
仓库中的 CI 产物按构建身份标记 `HARDWARE-UNTESTED`；已验收的组件不能使任意新产物自动成为实机通过的镜像。操作前阅读：

- [安装与升级](docs/installation-plan.md)：备份、包身份、写入范围、恢复和升级行为。
- [下载与发布包](docs/release.md)：首刷、日常升级、RAM 配套包和校验清单的获取方式。
- [临时网页首刷](docs/ram-web-install.md)：专用 RAM 安装环境和首刷顺序。
- [系统构建说明](openwrt/system/README.md)：内核、APK、无线和安装包的集成方式。
- [验证记录索引](verification/README.md)：按阶段查阅实机、模拟和 CI 证据。

## 源码构建

使用 Ubuntu 24.04 / WSL 的 Linux 文件系统、普通用户和 Python 3.11 或更新版本。
各原生 OpenWrt 工作流列出了其构建依赖。最小 Linux 诊断构建可按下列方式复现：

```sh
sudo apt-get update
sudo apt-get install -y build-essential gcc-arm-linux-gnueabihf \
  binutils-arm-linux-gnueabihf libc6-dev-armhf-cross bc bison flex \
  libssl-dev libelf-dev libncurses-dev device-tree-compiler u-boot-tools \
  cpio xz-utils pkg-config qemu-user qemu-system-arm shellcheck python3-venv
python3 -m venv .work/lint-venv
.work/lint-venv/bin/pip install ruff==0.11.13
export PATH="$PWD/.work/lint-venv/bin:$PATH"
make verify
```

`make verify` 输出独立最小诊断环境，并非完整 OpenWrt 安装包。
OpenWrt 集成入口见[构建架构](docs/architecture.md)和[官方来源说明](docs/openwrt.md)。
默认构建目录为 `.work/`，可用 `TASKBASE=/absolute/linux/build-root` 指定；
`JOBS` 控制并行度。源码版本、下载哈希、补丁和产物清单随构建记录，
工具只处理本地构建文件，不会因执行构建命令自动操作设备。

## 开发资料

[硬件依据](docs/hardware.md) · [eMMC](docs/emmc.md) · [SD](docs/sd.md) ·
[网口](docs/ethernet.md) · [USB](docs/usb.md) · [无线](docs/wifi.md) ·
[Docker](docs/containers.md) · [验证方法](docs/validation.md)

新增 Linux 文件维护于 `overlay/`，无线维护于 `wifi/`，OpenWrt 集成维护于
`openwrt/`；生成补丁不作为唯一修改入口。完整 RDA 驱动与固件参考纳入
`wifi/vendor/`，匹配运行固件和高安 fastboot 分别归档；完整 SDK、大型上游源码、
其他原固件、设备备份和串口原始日志不纳入 Git。贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，
许可与第三方来源见 [LICENSES/README.md](LICENSES/README.md)。
