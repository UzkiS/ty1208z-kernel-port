# 无线重复 radio 修复（2026-10-15）

本板只有一个 USB `1e04:8888` RDA5995 无线芯片。
`2026.10.15` 默认 RDA 配置使用旧路径 `platform/soc/f9890000.usb/usb1/1-2`，
实际设备位于同一控制器的 `usb2/2-2`。官方 `mac80211.uc` 根据路径判断设备是否已配置，
没有把这两条路径识别为同一硬件，因而另建 `radio1`、`default_radio1`。
第二个配置使用不适用的 `mac80211` handler，日志出现找不到 PHY；它不代表第二块无线硬件。

## 修复与配置保留

- 按 USB vendor/product、板载控制器和端口定位真实设备，不固定 USB bus 或 PHY 编号。
- 初次默认配置及 `05-ty1208z-rda-path` hotplug 在官方 `10-wifi-detect` 之前更新 RDA 路径。
- 仅清理同一实际路径、单个默认 AP 接口、保持默认参数且关闭的重复配置。
  自定义 SSID、已启用接口、额外选项和独立 USB 网卡均保留。
- 不改变无线启停状态，不迁移密钥到公开数据，不在普通探测中无条件写配置。
  配置与热插拔处理并发时使用锁，重复执行不反复改写配置。
- `2026.10.15` 已转为非公开草稿，停止公开下载；替代版本号为 `2026.10.15.1`。

## 实际验证

1. 使用真实 ARM UCI，覆盖旧默认重复项迁移、重复执行、保存的 STA 密钥、
   自定义 SSID、已启用接口、额外选项、独立 USB 网卡及不匹配 USB 身份。
   测试由最终 APK 事务打包过程执行，使用独立合成配置，不接触设备用户配置。
2. 实机从真实 APK 安装修复文件，文件 SHA-256 与最终发布根一致，APK 所有权可查询。
   配置已提交到 `/etc/config/wireless`，无待提交的 UCI 改动，只保留关闭的 `radio0`。
3. 实机两次加载/卸载真实 RDA 模块，触发 PHY hotplug；每次连续三次 `wifi config`，
   均不生成重复 radio，配置文件哈希保持不变。没有启用 AP 或重新进行 STA/AP 全套射频测试。
4. 使用设备上的真实 ARM ucode 解释器和官方 `mac80211.uc`，仅替换输入为合成 board/config：
   旧路径输出创建 `radio1` 的命令，正确路径输出为空，直接验证原问题及修复结果。
5. 最终 sysupgrade 通过实际设备 `/sbin/sysupgrade --test`；无线、磁盘管理 HTTP 页面均为 200，
   netifd 实时状态只有关闭的 `radio0`。本轮没有浏览器画面验收。
6. 与前版最终 root 逐文件比较，只有三个无线脚本和 APK installed 数据库变化。
   Linux、RDA 模块、固件及其他应用运行文件字节均相同。复用既有内存、存储和应用证据，
   没有再次执行整套系统升级或完整 1 GiB 首刷。
7. 普通 `reboot` 后仍只有关闭的 `radio0`，配置已提交，四核、SD 自动挂载及持久标记、
   Docker 自启均正常。DHCP 地址发生变化，经串口查询和原 SSH 主机密钥核验后恢复连接。

本地 `make lint` 及新包 parser/ARM/异常归档检查通过。另修正历史只读 eMMC
probe/shutdown 测试 harness 缺失 `CONFIG_HI3798MV100_EMMC_WRITE` 的定义；
使用实际内核源码的 ASan/UBSan 检查通过，未修改内核驱动或已发布内核二进制。

本地私有证据只公开哈希：

- 配置迁移：`bfff642ab8f161d9b9a0e8c4798581854e53e00cb0821813fe5d7162dc3e9c10`
- 两次真实 PHY hotplug：`333a36fc9b966686fdd1dddc6bc59f4179489bc97057bc119a5de3bd25dfd471`
- APK、最终升级包及 netifd：`b13af274063ca02d442c841717a88ea60aeff17461a83dbb927f12ed12ef0116`
- 普通重启后状态：`93c401291d9b2f57c06f5ccf8d4c272076cf449610a09160721c736a14aab927`
