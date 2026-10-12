# TY1208Z CA kernel port

[![Diagnostic CI](https://github.com/UzkiS/ty1208z-kernel-port/actions/workflows/diagnostic.yml/badge.svg)](https://github.com/UzkiS/ty1208z-kernel-port/actions/workflows/diagnostic.yml)

为天邑 TY1208Z 高安版 / Hi3798MV100 准备现代 Linux 板级适配，后续目标是
原生 OpenWrt/Kwrt、Passwall、板载 Wi-Fi，以及可验证的 64 位时间支持。

**当前是离线诊断候选工程，尚未在盒子上启动，不是可刷入的路由器固件。**
现有 fastboot 和 Hinas 没有被修改。状态见 [STATUS.md](STATUS.md)。

## 先做什么

Linux 6.12.112、单核、串口、GIC、自带 RAM 根文件系统和诊断 shell。
存储和网络驱动关闭，因此首轮不依赖也不会挂载现有 Hinas 分区。
QEMU virt 用同一个原始 zImage 验证通用启动和用户空间，使用它自己的设备树；
它不能验证本机定时器、USB、Wi-Fi、高安校验或内存布局。

初始设备树中的 256 MiB 内存范围只是待核实参数。uImage 的加载和入口地址
沿用本地 Hinas 的 `0x02000000`，并未证明这对本机的临时启动安全可用。
生成的镜像未签名、没有 ADVCA 封装。实际加载前必须核对硬件和当前引导。

## 构建与测试

在 Ubuntu 24.04 / WSL Linux 文件系统中构建，Python 3.11 或更高：

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

默认源码/编译目录是 `.work/`；可用 `make build TASKBASE=/absolute/work/path`
指定。上游压缩包按 [sources.lock.json](config/sources.lock.json) 校验 SHA-256，
构建脚本不访问盒子。环境变量 `JOBS` 控制并行度，`CROSS_COMPILE` 指定兼容工具链。
版本、时间戳、输入文件和哈希固定；不同编译器/主机包版本仍可能产生不同二进制。

输出在 `artifacts/diag1/`：

- `uImage-UNTESTED.bin`：附带 DTB 与 initramfs 的普通 legacy uImage。
- `zImage`：不带本机 DTB，供 QEMU virt 验证。
- `linux.config`、`busybox.config`、补丁、源码锁定表、`manifest.json`。
- `checks/`：镜像结构、ELF、工具链及 QEMU 结果。

CI 在干净环境执行相同构建，并提供名称含 `HARDWARE-UNTESTED` 的 Actions
产物。不会自动发布刷机包或执行设备操作。

## 项目边界

内核、无线和 OpenWrt 集成有各自的输入、依赖及验收边界。
当前内核构建独立于其他两层。目录和依赖见 [architecture.md](docs/architecture.md)，
硬件依据见 [hardware.md](docs/hardware.md)，Wi-Fi 线索见 [wifi.md](docs/wifi.md)。

已有 Hinas 的只读 SSH 基线见 [baseline.md](docs/baseline.md)。本机已确认
RDA USB `1e04:8888` 无驱动绑定；下一步先按 [TTL 记录步骤](docs/ttl-baseline.md)
核实当前引导器和 RAM 加载条件，再选择诊断候选的实际启动方法。

源码和研究说明可提交；原始固件、fastboot、DTB、源码下载和大体积编译产物
保存在本地。厂商参考只提交出处和哈希，可执行 `make references` 重新获取。

## 2038 验证范围

ARMv7 诊断用户空间使用静态 glibc、`_TIME_BITS=64` 和 BusyBox time64 配置。
QEMU 内测试 2040 年时钟设置/读回、日期转换、睡眠和 RAM 文件时间。
另有 BusyBox `stat` 的时间输出修复：原版仍会将 64 位 `time_t` 缩窄为 ARM32
的 `long`。这不代表现有 Hinas 程序、Passwall、代理核心、证书和 NTP 已验收。

## 贡献和许可

修改前阅读 [AGENTS.md](AGENTS.md)。许可证和第三方来源见
[LICENSES/README.md](LICENSES/README.md)，具体里程碑采用
[CONTRIBUTING.md](CONTRIBUTING.md) 中的验证要求。
