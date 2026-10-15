# 四核、全内存与磁盘管理实机验收（2026-10-15）

当前生产内核 Linux 6.12.112，官方 OpenWrt 固定提交
`58efa9917d4cc53fceed173529a286187649e827`。本报告覆盖新生产配置和 DiskMan 集成，
未重复已经通过且字节未变的代理、无线角色与 Docker 容器全套测试。

## 内核与内存

新 RAM 系统实测 CPU `0-3` 在线；`MemTotal=994384 kB`、`HighTotal=234576 kB`。
四个工作进程分别固定到 CPU0–CPU3，每个写入和验证 128 MiB，共 512 MiB，
完成地址相关与反相两种模式；父进程再次逐字交叉校验。
实际 pagemap 中 `high_pages=38718`，约 151 MiB 测试页高于原 768 MiB 上限，
PFN 范围 8192–262143。未见 OOM、BUG 或 Oops。

完整 1 GiB 地址范围启用 HIGHMEM；低 16 MiB 和本次引导器的 11 项 allocation
逐项保留。没有把引导器正在使用的页算作可用内存。

## 普通存储读写与持久升级

SD 与 eMMC p9 分别完成 4 MiB 随机文件写入、卸载、只读重新挂载、SHA-256 读回和清理。
SD 写计数增加 38 次 / 8230 扇区，p9 增加 47 次 / 8528 扇区，未见 I/O 或文件系统错误。
生产队列为正常 256 KiB 多块路径，CMD17/18/24/25；未宣称 DMA 或高速总线已适配。

普通重启后发现合法 p9 元数据 CMD25 被请求策略拒绝，Linux 以单块重试完成，
没有出现 ext4 错误。Linux 6.12 的 `REQ_META` 可携带 `MMC_DATA_DAT_TAG`；
无 CMD23 能力时该标记只是软件提示，不改变线上写命令。
生产策略已接受这个标记，并对所有带 WRITE 位的请求保留完整 p6/p9 范围检查；
可靠写入、跨分区和受保护区域仍拒绝，实际策略 ASan/UBSan 回归通过。

修正后的内核通过保留配置的真实 sysupgrade 启动。
128 个文件的创建、chmod、改名、硬链接、逐个内容核对、删除和三次 sync 实测通过，
产生 39 次写请求 / 1952 扇区；新启动和该负载前后均为零条被拒绝的 CMD25，
无 I/O、ext4、Oops 或 panic 错误。这验证了所测元数据负载的修复结果，
未将对旧请求标记的源码推断写成逐请求硬件跟踪。

从原持久系统运行真实 `/sbin/sysupgrade --test` 后进行保留配置升级。
stage2 释放 p9、文件级更新并逐文件读回、p6 读回后默认从 eMMC 启动。
新内核、精确模块、ext4 rw 根、用户持久标记和 Docker `/opt/docker` 均核对通过。
升级时 Docker 启动脚本调整了重复的 firewall network list；网络含义不变。
DiskMan 的 LuCI 基础依赖安装补充了官方 uhttpd ucode handler，未改变用户密码或管理密钥。

## LuCI 磁盘管理

固定 DiskMan `c20df1d4f40d86e32fd919f33122b2a48f8a99b4`，本板 APK `0.2.13-r3`。
包含简体中文、parted、e2fsprogs、dosfstools、exfat-mkfs/exfat-fsck、blkid、smartmontools。
实际持久系统通过 HTTP 登录后验证：

- `admin/system/mounts` 返回挂载页，标题“挂载点”。
- `admin/system/diskman/disks` 返回中文磁盘及挂载表单。
- `admin/system/diskman/partition/mmcblk1` 返回 SD 分区及 ext4/FAT32/exFAT 格式化选项。
- 通过 LuCI 格式化后端将获授权的 SD p2 依次格式化为 FAT32、exFAT、ext4；
  每种均正常挂载、写入 4 MiB、卸载后以只读重新挂载，SHA-256 一致。
- 通过 DiskMan CBI 表单的真实 POST 完成 ext4 挂载与卸载。
- 已挂载 SD 分区的格式化返回 HTTP 409；系统 eMMC、p6、p9 同样返回 409。
  修改分区表要求带 LuCI token 的 POST，GET 被拒绝。
- 实际 ARM Lua 运行板级策略测试，覆盖别名、子分区活动挂载、swap、holders、只读
  和信息缺失时拒绝，SD/USB 数据盘放行。

SD 最后保留 ext4 p2，配置 UUID 自动挂载到 `/mnt/sdcard`。
一次普通 `reboot` 后再次确认四核、994384 kB MemTotal、DiskMan APK、三个 HTTP 页面、
SD ext4 rw 自动挂载与持久文件、用户持久标记、Docker 数据目录均保留。
串口核对 11 项 allocation、四核启动、SD/USB shutdown 完成标记，无 panic 或 ext4 错误。
这里验证的是 HTTP 页面与后端行为；没有把浏览器画面渲染写成验收结果。
随后包含元数据修正的完整升级也保留了上述自动挂载、持久标记和三个 HTTP 页面。

## 交付身份与验证范围

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| 生产 zImage | — | `18a7efd40a08291a551f37ca47354278de460b9e7cb0d1db2844ef68b7e12f6c` |
| p6 kernel | 4925410 | `c2b72c4dd56705a93ead0d54a3151d3f1dbe934e0938d1ea5632743c109f135c` |
| 运行 RDA 模块 | 317980 | `3eb398b1c6495d8385c3a026ae4c4874a8dad029053789b12596ab9dc2981ffd` |
| Release sysupgrade | 131379402 | `b0f21dd0865677eba39b2b85e78784f66c9f93a428f4230de57055b433d9bf28` |
| Release first-install | 132362441 | `744edb18b79cfd8f423e51603edb1e8782192d4036b9e7253d214dce9a51ce75` |

ABI：`6.12.112~0757bd0e5fb295b399d4be7ea0c4decb-r1`。
最终 sysupgrade 通过实际设备 `/sbin/sysupgrade --test`、主机 ASan/UBSan 上传/归档
异常检查、实际 ARM parser 检查；DiskMan 关键安装文件与最终系统根逐文件匹配。
包含该内核和 DiskMan 的镜像已完成真实完整升级；最终发布包另做构建路径映射和
调试信息处理，改变的应用二进制单独验证，不重复整个系统升级。
first-install 未重复整个 1 GiB 首刷。四核内存模式、SD 三种格式和无线 STA/AP
复用此前验收；最后修正不改变这些驱动的资源与内存布局。

最终发布根的十个变化运行文件（C++ 运行库、升级后端和 Docker/containerd 组件）
已用离线 APK 安装到实机并逐一核对 SHA-256。运行中的 dockerd 和 containerd
从 `/proc/PID/exe` 再次核对，均匹配发布文件。一个本地 ARMv7 小容器通过
只读根、无网络、64 MiB 内存、0.5 CPU、32 PID 和 seccomp 模式 2 检查；
smartctl、btrfs 版本查询正常。最终 sysupgrade 再次通过实机 `--test`，
三个存储 HTTP 页面正常，无新增 CMD25 拒绝或文件系统错误。

USB 的既有只读文件证据继续有效；本轮未格式化 USB，未新增其写入速度或热插拔验收。
SD 格式化证据不自动延伸到其他文件系统、容量与 USB 硬件。

本地私有收据按 SHA-256 留存，不公开原 UART、网络身份或凭据：

- 512 MiB 内存日志：`0234519adf2d66d59cebc0b498931224a0d88613b8283df5a188cec5665c1843`
- 普通读写日志：`283af22bc56a398f958ac4d3b69e1e3dc4ffff3b76136c59c881cc21198c4c66`
- 持久升级串口：`53dc4a4343315d0f06051d17079a795badec1fa5e63ed1e6e4a29a5d426e4df2`
- DiskMan 重启后状态：`dab5b3ba837dd69e9851b59b2f088611bb7e8b904ffa30aad75deb6703353283`
- 元数据修正升级串口：`47623f02aef6eb6a931aafd928d9936e92d169e2860203503ae55155c593852c`
- 元数据负载与升级后状态：`8b97fe06e541983b9ae7c9cdbf30e9d120c2e7753305510d358149c1982176dd`
- 最终运行文件与小容器：`866bad2fdaf22355de49e6ebfd814f4055b279ab4e58a5c67b6ac3a35572115a`
