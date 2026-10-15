# Docker 构建与运行

当前持久系统包含 Docker/dockerd 29.6.1、containerd 2.2.5、runc 1.3.6、
tini 0.19.0、Compose 和中文 Dockerman。小型 ARMv7 容器、资源限制、默认 seccomp、
DNS 和物理网口 HTTP 已实测；容器数据位于 `/opt/docker`，
跨断电保留和 Docker 冷启动自启通过。
见[系统实测](../verification/openwrt-system-board-20261014.md)和
[持久升级实测](../verification/native-web-upgrade-board-20261015.md)。

## 使用边界

CPU 是 32 位 Cortex-A7，应使用 `linux/arm/v7` 镜像；ARM64 镜像不能原生运行。
此前容器实测基于单核、约 744 MiB 可用内存；生产配置已开启四核和完整 1 GiB 地址范围，
可用内存仍需扣除内核与实际引导占用，新配置的容器并发性能待实测。
磁盘根的 Docker snapshotter 是 overlayfs；早期 RAM 容器实验的 overlay2 结果
属于相应实验版本。大镜像、外部仓库、IPv6 和综合吞吐未全部验收。

## 独立构建入口

先完成 `make openwrt-toolchain`；下列命令均接受
`TASKBASE=/absolute/linux/build-root`。

| 入口 | 验证内容与输出 |
|---|---|
| `make openwrt-container-config` | 解析并核对包选择 |
| `make openwrt-container-packages` | 构建真实 APK，核对 ARM EABI5、来源和 qemu-arm `--version`；不启动 daemon |
| `make openwrt-container-qemu` | 先完成诊断 `make build` 和容器包构建；隔离 ARMv7 QEMU 测容器运行 |
| `make openwrt-container-applications` | 同一原生根中组合 fw4、Passwall 双核心和容器运行 |
| `make openwrt-system` | 将已验收原生归档和本次板级内核组合成 RAM 系统 |

容器配方和源码身份由 `openwrt/containers/sources.lock.json` 固定。
独立 package profile 把包选为 `m`，只提供编译产物；
其内核依赖包含 block/Btrfs、namespace、cgroup、seccomp 和 nft NAT，
但不启用板载 MMC/USB/网口或 SMP，不能作为安装镜像。
曾缺少 `kmod-nft-nat` 导致 Docker iptables-nft 无法创建 NAT 链；
实际配置检查现覆盖这项依赖。

## QEMU 验证范围

独立容器 QEMU 使用 Cortex-A7、768 MiB，无磁盘、主机挂载或物理网络。
真实容器测试 PID/hostname 隔离、overlay2、默认 seccomp、CPU 限流、
memory-cgroup OOM、可写层、生命周期和清理；
guest-only namespace 验证 bridge DNS/HTTP、masquerade 和发布端口 DNAT。
未来时钟只存在于 guest。该 profile 使用独立防火墙依赖，不代表 fw4/Passwall 组合通过。

组合 profile 使用真实 netifd/fw4、dockerd/procd 和 tini，
从容器 network namespace 运行原生 curl，验证两种 Passwall 核心的透明 TLS 流量；
关闭代理前后的直连必须失败，并检查重载后 Docker 网络和服务关闭。
原应用检查保留中文/空密码、DNS/TLS、双核心、unzip 和 NTP/time64。
26 个必需 marker 与精确 kernel/rootfs/fixture/console 哈希绑定。

较大的组合根先以 ramfs 展开，再由仅 QEMU 启用的入口逐文件复制并删除到 tmpfs，
避免同时保存两份完整根导致 768 MiB 全局 OOM；随后启动原生 `/sbin/init`/procd。
原归档和 `/init` 不修改，但测试入口不再执行原 `/init` 的整根复制路径。
新全局 OOM 直接判失败，不能以局部成功 marker 掩盖。
历史结果与最新干净 CI 分别见
[组合报告](../verification/container-applications-qemu-20261014.md)和
[CI 记录](../verification/ci-closure-20261015.md)。

## 系统集成

`prepare_native_userspace.py` 从已有原生归档生成 supplement；
最终离线 APK 事务登记包和本次内核模块，不能直接把独立容器内核模块复制进板级系统。
模块平铺目录、WAN/Docker 防火墙区域及冷启动预读/有界重试均在系统层整合。
安装、升级保留数据的具体目录见[安装说明](installation-plan.md)。
