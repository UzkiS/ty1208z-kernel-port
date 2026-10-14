# OpenWrt 应用构建与 time64 验证

`apps` 子目标构建真实 ARMv7 musl 应用，并在隔离 QEMU 的 2040 年时钟下运行。
独立应用 profile 输出 raw kernel 和 initrd；`openwrt-app-ram` 另行封装 RAM 候选。
当前持久系统复用应用层，安装状态见[状态页](../STATUS.md)。

## 固定输入与实际选择

`openwrt/applications/sources.lock.json` 固定 packages、LuCI、Passwall 和
Passwall packages 完整归档。Passwall 26.10.4 选择 Xray 26.10.10 与 sing-box 1.14.3，
后者明确使用 Passwall feed 的配方；InfoZIP unzip 6.0-r9 来自官方 packages。
其他代理核心和 geodata 关闭。RAM profile 关闭 Tailscale、ACME 和 gVisor，
保留 QUIC、uTLS、WireGuard、Clash API 的配方默认值。

工具链复用原生 GCC 14.3.0/musl 1.2.5并记录身份；Xray 所需 Go
由固定 packages 中的 1.27.1 配方提供。
Passwall Lua 的检查式补丁把自定义 CA 改为 Xray 要求的 `certificates` 数组，
保留主机名及证书过期验证。

简体中文 LuCI、防火墙和 Passwall 翻译包随根安装，首次启动设 `zh_cn`；
root 默认为空密码。检查器核对真实 LMO、已安装包和 shadow 字段。
测试先验空密码登录，再仅在 guest 设置临时密码测试认证。

## 复现

在普通用户的 Linux 文件系统中，按
`.github/workflows/openwrt-applications.yml` 安装依赖后执行：

```sh
make openwrt-toolchain TASKBASE=/absolute/linux/build-root
make openwrt-app-config TASKBASE=/absolute/linux/build-root
make openwrt-applications TASKBASE=/absolute/linux/build-root
make openwrt-app-ram TASKBASE=/absolute/linux/build-root
```

源码和输出位于 `TASKBASE/applications/`；下载可复用，配置与其他变体分开。
`checks/applications-qemu.json` 绑定真实 kernel/config/initrd、包清单、
console 和工具链哈希。干净 CI 的实际结果见[CI 记录](../verification/ci-closure-20261015.md)。

## 运行验证

- libc 时间转换、文件时间、BusyBox、日志、dnsmasq、OpenSSL 与 curl/mbedTLS。
  2040 年有效证书必须通过，过期或不可信证书必须失败。
- LuCI 受保护页面、空密码与密码登录、rpcd session、已认证 Passwall 页面和真实 Lua API。
- 安装的 Passwall 控制器生成并启动 Xray/sing-box SOCKS 与 VLESS/TLS，
  真实 HTTPS 内容通过有效自定义 CA 链；过期代理证书必须失败并出现过期日志。
  仅对已知 loopback 控制器返回码作受约束处理，同时仍要求配置及数据流成功。
- InfoZIP 解压 stored/deflated、中文 UTF-8 文件名、ZIP64 local header、空文件和
  2040 时间戳，核对内容哈希。
- 安装的 BusyBox NTP 客户端连接 guest-only 服务端，跨 2036 era、2038 边界及
  2026 → 2040 校时，读回实际结果；[NTP 记录](../verification/openwrt-ntp-time64-20261013.md)。
- nft 实际回环计数及 socket/TPROXY 规则插入；这项本身不等于透明转发通过。

默认 Cortex-A7 QEMU 使用 512 MiB；RAM 打包另用256 MiB和 `mem=240M`，
保守计入低16保留。guest 无磁盘或主机网络，写入、临时密码和未来时钟只在 guest。
这不是实际板上内存性能或所有协议的覆盖。

## RAM 打包与网口变体

固定 libdeflate 1.25 host 工具以 level 12 压缩排序后的 newc，无 gzip 时间戳；
检查器比较解压内容与原 cpio。
应用根不能嵌入低16解压范围，因此独立 DTB 指定 initrd 起点 `0x04000000`，
压缩上限32 MiB、展开上限96 MiB。曾尝试36 MiB，但 TFTP 不支持块号回绕，
传输检查拒绝；不能只因 RAM 放得下就放宽传输门禁。

`make_openwrt_apps_ram.py` 保留已测 kernel/rootfs/modules，检查240 MiB QEMU证据、
板级来源和外设禁用。RAM 规划器再检查实际引导器身份和 DDR，
串口工具分别传输 kernel/initrd，两个设备 CRC 都通过才发送固定 boot 命令。
输出 `artifacts/openwrt-apps-ram1/` 不包含板载网口、存储、USB 或 SMP，
不提供安装后端。

独立[应用与网口变体](openwrt-router.md)另测 netifd/fw4 和真实 TCP/UDP TPROXY。
实机与 QEMU、普通应用与完整系统的证据保持区分；
[历史应用记录](../verification/openwrt-applications-20261012.md)保留其当时范围。
