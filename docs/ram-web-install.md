# 临时 OpenWrt 网页首刷

2026-10-15：本方案已实现并完成一次实机首刷。TTL 加网线启动临时 RAM OpenWrt，
随后使用官方中文 LuCI 上传专用安装包，无需 SD。安装后的升级继续走官方
LuCI/sysupgrade，详见[持久安装与升级](installation-plan.md)。

## 使用流程

1. 保留原 CA fastboot。TTL 截停后，核对芯片、1 GiB DDR 和完整 11 项 allocation；
   沿用已测地址/命令，TFTP 装载精确安装 RAM 内核和 bootstrap，核对设备 CRC。
2. 临时系统上线后安装匹配 APK 补充包和 first-install 后端，打开官方中文 LuCI
   “系统 → 备份与更新”。普通只读 RAM 固件不能直接作为安装器。
3. 上传 first-install 包，核对 SHA-256，选择是否保留配置，再确认。
4. 官方 stage2 切 RAM，写入 1 GiB p9，flush/完整读回；恢复配置后写入/读回 p6、
   锁回只读，再重启。
5. 使用现有 eMMC p6 加载路径启动，在线扩容至 6846 MiB p9。分区表和持久
   boot 环境不变；后续使用 sysupgrade 包。

已完成安装的设备使用后续升级流程。first-install 与 sysupgrade 格式不同，
后端会拒绝错误场景，没有强制绕过板型/布局检查的入口。

## 实测与交付边界

中文 LuCI 上传、官方校验、RAM pivot、1 GiB p9 哈希读回、p6 读回、ext4 rw 根启动、
完整在线扩容及配置/Docker 冷开机保留已通过。首刷写 p9 约 29 分钟、读回约 11 分钟。
底层单扇区 PIO 仍是速度瓶颈；网页入口改善操作和写入量，不代表高速 MMC/DMA。

最新私有首刷包为 132,372,681 B，SHA-256
`895305f7d0bf2200dbb3bb6b7641e5ae50136d770f3fd861add18e65ac2d4e76`。
内核 ABI `6.12.112~120d00c44db5befcdb6ed8d1f6825a56-r1`，大小 4,677,436 B。
最新全包未再次覆盖设备首刷，复用已测流程及改变的扩容/内核/应用边界证据；
文件名保留 UNTESTED，避免把离线重打包写成完整实机重刷。

紧凑 ext4 扩容不会安全擦除 p9 未覆盖的旧空闲区域。仅替换 p6/p9；保留
CA fastboot、其他分区、SD、boot0/boot1/RPMB，不涉及 OTP/eFuse/security 写入。
原始 RDA 固件、备份、凭据及 UART 日志只保存在本地私有目录。

## 官方源码与 HiTool

官方 OpenWrt 25.12 固定提交 `58efa9917d4cc53fceed173529a286187649e827`，
LuCI 固定提交 `8125d1288b359f6df505d3328b712bf059843fc8`。后续文件级升级保留
Docker/用户数据，官方“保留配置”负责恢复配置。

本地 HiTool 有 Hi3798MV100-CA 定义和 HiBurn 文档，但现有 fastboot 检测兼容性及
HiTool p6/p9 刷写未实测，不作为已验收默认流程。
