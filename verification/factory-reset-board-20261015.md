# ext4 恢复默认实机验收（2026-10-15）

## 改动和构建身份

系统直接挂载 p9 ext4 可写根，没有可清理的 overlay 或 rootfs_data。
上游 LuCI 因此隐藏恢复按钮，上游 factoryreset 也不能完成该操作。
新增独立中文页面“系统 → 恢复默认设置”和 `ty1208z-reset` APK，保存构建时的干净 `/etc`。
固定 fstools 版本及原 ELF SHA-256 的检查式适配将 factoryreset / firstboot / jffs2reset 接到板级后端，
保留 mount_root、库、软件包许可、元数据和脚本，修改后的文件仍由真实 APK 拥有。

默认快照带文件哈希、软链接清单和 ABI 校验。请求阶段只准备事务，下一次 preinit 在服务前通过
renameat2 RENAME_EXCHANGE 原子切换 `/etc`；持久 token 区分交换前后，禁止再次交换回旧密码。
保留本机网口 MAC、SSH 主机密钥与 APK world，清除登录授权和旧密码。恢复不写 p6，不格式化 p9。
有待执行重置时拒绝同时升级固件。首刷快照包含对应 grow APK 文件，但不重新安排扩容。

sysupgrade 131,850,442 B，SHA-256
`c1735d1b99a75d5a8af5bc0bd61adc41e773340e3a2695a3b78522c80360ff0e`。
内核 ABI `6.12.112~0757bd0e5fb295b399d4be7ea0c4decb-r1`，p6 内核及 RDA 模块与 `.2` 相同。
与 `.2` 的原 root 逐项比较，现有文件只改变 etc/apk/world、lib/apk/db/installed、lib/apk/db/scripts.tar.gz、
sbin/factoryreset 和 sbin/ty1208z-upgrade；新增恢复默认 APK 的后端、页面、预初始化钩子和快照。
内核、驱动、固件和应用二进制没有变化。

## 本次实际验收

- 最终 sysupgrade 中相同的 fstools、reset、upgrade APK 安装到当前盒子；检查所有权、后端预检和默认快照。
- 通过 CLI/HTTP 检查中文 LuCI 路由 HTTP 200、页面 JS 与仓库逐字节一致，以及页面使用的真实 file.exec RPC。
  没有使用 Computer Use，也没有将 HTTP 路由检查声称为浏览器人工点击验收。
- 准备非空测试密码、自定义/关闭的无线设置、额外配置与 root 登录授权，并记录 SD、Docker 和用户数据哈希。
- 调用 LuCI 相同的 `/sbin/ty1208z-reset -y -r` RPC，返回 code 0；普通命令重启。
  串口观察到原子重置完成，随后系统正常启动。配置验证在串口执行，没有为测试保留 SSH 授权。
- root shadow 密码字段为空，LuCI 空密码登录通过；旧密码散列、自定义配置、Dropbear 和 root 的登录授权均清除。
  rpcd 在 root 空密码时允许任意提交字符串，因此没有把“旧字符串登录被拒绝”作为验收标准。
- 本机 Ethernet/bridge MAC 和 SSH 主机密钥哈希保持；一个开启的 radio0、TY1208Z 开放 AP、br-uplink 桥接与主路由 DHCP。
  LAN 防火墙区与 Docker 的对应转发规则恢复默认。
- Docker daemon 正常，/opt/docker 和用户标记哈希相同；SD 在临时只读挂载点读取，内容哈希相同，然后卸载。
  挂载和服务设置清除是预期行为；数据保留不代表原自动挂载或容器策略全部保留。
- firstboot / factoryreset / jffs2reset 的 --check 均到达同一后端。
- 再作一次普通命令重启：boot_id 改变，MAC、DHCP 地址、网络/无线/DHCP 配置、空密码与 SSH 主机密钥的组合哈希保持一致，AP 再次自启。
  p6 仍只读；四核正常，无 Kernel panic、Oops 或 ext4 I/O 错误。

## 离线与复用范围

make lint 通过。`test_native_reset.py` 使用真实 ARM UCI 和实际原子交换，隔离验证正常事务、
交换后中断不回滚、准备中断不修改原配置、损坏快照/软链接/事务目录和 /etc 子挂载拒绝，
密码与授权清除及设备身份、软件包 world、用户/容器/SD 目录保留。
sysupgrade 的主机 ASan/UBSan/异常归档、实际 ARM parser 通过；首刷根的对应快照测试和 ext4 检查通过。

未再次覆盖 1 GiB 首刷，未进行整套 sysupgrade，也未在实机反复断电；复用已通过的安装、内核、
内存、存储和应用证据。物理复位按钮未验收。完整范围见[用户说明](../docs/factory-reset.md)。

## 私有证据身份

原始配置、凭据、网络身份、UART 和细节只留在公开 Git 之外。

| 证据 | SHA-256 |
|---|---|
| 实际 APK 安装和所有权 | `9e0ad4894b1edf37d2520b0310ad297b00d999d80af9d63ec009f15aa139f5d7` |
| 实际重置 RPC | `34b7695fdffa219aa6f6220dbfc329bc8bc07435c280824e6db8cef7e3894949` |
| 重置启动 UART | `65e1449cb1f01cf57fb79e1f129c0bd48d926dcbf655b519a52846295c41b361` |
| 重置后配置/数据/身份检查 | `b5d829ebe552a0617161a915c35b82e5d7a2c8285cdc360209f8a77a4aa6e13c` |
| 重置后普通重启 | `903845355c8169fc9af14a4e66b29299073081ec9e4dfde1a9211c26dca6f131` |
| 重启后持久化检查 | `8354a55b0b0b0e61fb1226afde4d9d627d30cc18fc828bb386c731030f8a961f` |
| 测试结束与授权清除核对 | `32a8e8eaabacd2c093e2722aec3e69b542915b2a3b965fa1b6f960a99fc7f9b0` |

本轮结束时未重新安装测试 SSH 登录授权，设备保持 root 空密码和 TY1208Z 默认桥接热点。
新增 LuCI JS 的隔离执行检查还覆盖确认前不请求重置、后端失败提示、只读/预检失败禁用和当前地址重连；没有把它当作实机浏览器点击。
