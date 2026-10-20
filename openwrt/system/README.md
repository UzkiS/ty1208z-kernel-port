# 原生 OpenWrt 系统集成

本目录维护 TY1208Z CA 的系统组合：四核 SMP、HIGHMEM、1 GiB 地址范围、网口、SD/eMMC、Docker、
中文 LuCI、Passwall 双核心、unzip 和 RDA 无线。**持久安装、在线扩容、原生网页升级及
普通重启已通过实机验证**；新四核、全内存与多块队列的实机状态单独记录，
见[当前状态](../../STATUS.md)和[安装说明](../../docs/installation-plan.md)。

完整固件使用 `make openwrt-release-full VERSION=...` 默认生成 `bridge`、`hybrid`、`nat`
三版，共用内核与应用，分别制作首刷/升级包及恢复默认快照；
详见[网络版本与构建入口](../../docs/network-variants.md)。以下桥接默认说明适用于 `bridge`。
`2026.10.20` 的三版正式下载与校验身份见[发布记录](../../verification/release-20261020.md)，
混合版和 NAT 版尚未实机联网验收。

## RAM 开发系统

先完成固定原生工具链、`openwrt-router-emmcro` 和
`openwrt-container-applications` 用户空间，再执行：

```sh
make openwrt-system TASKBASE=/path/to/existing/taskbase
```

默认读取 `TASKBASE/router-emmc/build/openwrt-ram-<pinned-commit>`；
`--native-source` 可指定已有基线。`kernel.config` 维护系统内核配置差异，
`toolchain_from_native` 核对实际编译器。所有模块来自本次内核，不能混用其他 target。

生产 RAM profile 提供 SD/USB 普通读写与 eMMC p6/p9 多块读写；历史只读诊断独立保留。
bootstrap 在已测传输和展开预算内，
较大用户空间由 SSH supplement 提供。模块直接放在 `/lib/modules/6.12.112/`，
因为 ubox kmodloader 不递归 `kernel/`。离线 APK 事务登记包与所有模块的归属。
首次默认配置把网口和 AP 放入 `br-uplink`，`probe` 继续作主路由的 DHCP 客户端；
桥加入 LAN 防火墙区，允许主路由 DHCP 和同网段管理，Docker 转发到该 LAN 区。
保留已有无线配置的升级不会自动修改无线模式或网络布局，旧路由型配置仍沿用 WAN 区。

`--resume` 只复用已经检查的构建目录；保留已完成产物时使用新的 `--work`/
`--output`，打包器拒绝覆盖完整交付清单。构建工具不连接物理设备。
RAM 启动仍要求精确 `system` profile、新引导分配表和双设备 CRC；
RAM 包本身不作为持久安装包。早期验收见[系统 RAM 报告](../../verification/openwrt-system-board-20261014.md)。

## 无线与管理

`ethernet-mac` 在 netifd 启动前把每台设备自身的随机 fallback MAC 写入 UCI，
后续启动复用，桥也沿用这个地址；保留用户指定 MAC，不把真实设备地址写入公共镜像。
它稳定 DHCP 身份；需要永久固定 IP 时仍应在主路由保留租约。

`wireless/rda.sh` 管理单个无线接口的进程、模块和固件切换。
`wireless/rda-path` 在默认配置和 IEEE80211 hotplug 自动探测前按实际 USB 路径定位板载芯片，
避免 EHCI/OHCI 总线编号变化产生重复 radio；仅清理同一硬件未修改且关闭的默认重复项。
角色切换在用户空间完成，避免在 cfg80211 持有 RTNL 时重枚举 USB。
支持一个 AP 或路由型 STA、2.4 GHz、HT20/legacy、开放或 WPA2-PSK/CCMP、
固定 AP 信道；首次安装/恢复默认开启无密码热点 `TY1208Z`，与网口桥接。不支持桥接 STA、mesh、WPA3、TKIP 或多接口。

`tools/luci_rda_wireless.py` 对固定官方 LuCI 表单作检查式适配；
`tools/netifd_wireless_eof.py` 修复 handler discovery 的 EOF 循环。
STA、AP 与角色切换的具体版本边界见[无线报告](../../verification/rda-wireless-board-20261014.md)。
RDA 固件已获项目所有者授权公开，归档于 `firmware/rda5995/` 并随完整 Release 发布，
精确来源和哈希见其 manifest。完整 63 文件的驱动和 USB/SDIO 固件参考同时保存在
`wifi/vendor/rdaw80211/`，默认直接从仓库读取。打包脚本默认包含匹配运行固件。

## 持久候选与恢复工具

`build_native_system.py --persistent-candidate` 使用独立输出树，只允许已测 p6/p9 范围。
`prepare_native_disk_root.py` 用精确内核和 APK 生成 ext4 p9 与 disk-root uImage，
只处理文件。生产内核始终采用同一份多块读写策略，持久打包标志不再改成单扇区实验驱动。

`probe_native_emmc_write.py` 保留历史单扇区写入/读回/恢复计划，供已有证据回归；
`install_native_emmc.py` 默认生成离线校验计划。`--apply` 会实际操作存储，
应只用于已建立备份、恢复条件和精确设备身份的安装。
安装器先 p9 后 p6，清块缓存后作 SHA-256 读回，再锁回受保护分区；
`--mode restore` 仅恢复备份对应的 p9 范围和 p6 内容。
单扇区恢复、紧凑安装和 eMMC 根启动已实测；完整原系统写回恢复没有重复实测。

## 官方网页升级

持久系统安装真实 `ty1208z-upgrade` APK，提供 `/lib/upgrade/platform.sh`，
沿用官方 LuCI“系统 → 备份与更新”和 `/sbin/sysupgrade`。
校验设备、布局、uImage CRC、根归档和空间；差异在写入前拒绝。
官方 stage2 切入 RAM，确认进程、namespace、loop 和 swap 不再引用 p9，
再 staging 根文件并逐文件核验，更新/读回 p6 后重启。

归档只包含受管系统目录。`/opt`（含 `/opt/docker`）、`/root`、`/home`、
`/mnt`、`/srv` 保留；“保留配置”恢复可信备份到新 `/etc`，
取消该选项使用镜像默认配置，但仍保留数据目录。
失败事务留下恢复记录，不能盲目删除旧根或重启。
流程及普通磁盘根重启已实测，见[升级报告](../../verification/native-web-upgrade-board-20261015.md)。

## 紧凑网页首刷

`make openwrt-first-install` 从已准备的新根和精确 disk-root 内核生成首刷包。
输入位于其他目录时设置 `NATIVE_SOURCE`、`UPGRADED_ROOT`、`DISK_ROOT` 和 `OUTPUT`。
匹配的 `ty1208z-first-install` APK 只用于专用临时 RAM 安装环境。

首刷写入 1 GiB ext4 p9，完整验证后激活 p6；
`ty1208z-firstboot-grow` 在首次磁盘启动扩展到完整 6846 MiB。
后续升级使用独立文件级 sysupgrade 包，不能再次用首刷包替代日常升级。
[首刷报告](../../verification/compact-first-install-board-20261014.md)记录完整实测；
最新全包只复用该流程，未再覆盖首刷，变化的内核由日常升级验证。

## ext4 恢复默认

`tools/native_reset.py` 为持久系统生成真实 `ty1208z-reset` APK，保存当前固件的干净 `/etc`、
文件/软链接校验清单、LuCI 页面和 preinit 后端。`prepare_native_upgrade.py` 安装该包并检查式
重打包固定 fstools；`prepare_native_first_install.py` 在安装扩容 APK 后另生成相符的默认快照。
`firstboot` / `factoryreset` / `jffs2reset` 最终调用同一个板级后端。

请求阶段保存本机 MAC、SSH 主机密钥和 APK world；下一次 preinit 在服务启动前原子交换
完整 `/etc`，清除 `/root/.ssh` 的登录授权，回收旧配置。事务 token 防止掉电重入时回滚。
不清理 `/opt/docker`、SD 或用户数据，不写入 p6，也不借用 overlay 擦除。
后装软件新增的 `/etc` 文件恢复为固件默认范围，可能需重新配置或安装；不等同于软件文件回滚。

隔离事务、异常快照、交换前后中断、真实 ARM UCI 和实机重置结果见
[恢复默认报告](../../verification/factory-reset-board-20261015.md)，用户入口见
[操作说明](../../docs/factory-reset.md)。实体复位键尚未验收。
