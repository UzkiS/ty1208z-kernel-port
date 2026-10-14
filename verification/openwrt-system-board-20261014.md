# 完整 RAM 系统与物理 Docker 实测（2026-10-14）

> 历史阶段记录：本页只描述此RAM镜像的实测。后续持久安装状态见 [STATUS](../STATUS.md)。

单一RAM系统通过OpenWrt procd运行原生ARMv7 Docker29.6.1与小容器，
使用overlay2、cgroup v2和默认seccomp。
容器经LAN gateway解析DNS、通过物理网口执行TCP/HTTP请求均通过。
SD/eMMC全程请求级只读，没有卡、flash或持久boot写入。

## 精确产物

- TY1208Z CA / Hi3798MV100，一个在线Cortex-A7。
- Linux6.12.112 SHA-256：
  `b474bd8fc834cc8e9091159fe81855f46e63e4c70aef368cb3a324626d4b3ac4`。
- 实际config SHA-256：
  `cce1bcb5838add7f35d31a3485c0b8f62aabe9bfbbb6ab81c4aa71db0f28a163`。
- Bootstrap压缩22561748 B、展开61516800 B，SHA-256：
  `3202c092c7e4305bb45e6e69bd992e3abdd6a19584763f85b3009ff102519b27`。
- MemTotal762296 KiB，约744 MiB；新受控重启allocation证据支持低768范围，
  低16保留、上方256排除。
- eMMC `008G30`：7818182656 B、九分区、只读；
  SD `SU04G`：3965190144 B、两分区、只读。
- 双存储controller与内置受控restart绑定，IRQ Err0。

设置时核对中文、root空密码及应用/runtime文件身份。
已有双代理核心、unzip、time64、应用网络和较大内存证据复用，
没有重新执行整套测试。大supplement通过SSH直接解入RAM。

## 集成修复与实测

最初模块位于 `lib/modules/6.12.112/kernel/...`，
但ubox kmodloader只扫描release目录；平铺本次107个模块后加载正常，
未复制其他target模块。

随后daemon和容器已启动，但DNS转发失败：DHCP接口probe不在WAN，
且没有Docker → WAN转发。
把实际uplink加入WAN并增加转发后成功，保留防火墙；
默认值维护于 `openwrt/system/docker-network`。

最终实测tmpfs上的overlay2、ARMv7、64 MiB memory limit、
CPU quota读回 `50000 100000`、容器PID1和seccomp mode2。
通过gateway解析 `openwrt.org`，并从主机经物理网口取得唯一HTTP token。
私有runtime SHA-256：
`204a15c7108cac6659895628cba0b8a6b9a045424b500d2d448ec625b69a1675`。
失败尝试原始记录均在清理前保留本地。

删除容器、停止Docker后恢复原三份UCI。
双MMC host实际关闭，命令重启到新CA引导，
原router双设备CRC通过并恢复配置。
中文认证LuCI、root空密码、restart模块及IRQ Err0均通过，无人工断电。
私有restart SHA-256：
`2b3073766e7b7ecbc56d295311addc533f3c66e49a369ac4489b7437432eb193`；
恢复健康检查：
`30513a1cddf4eb8d0240e00279afa970d8a670e28640e8df4afe4d6586f02369`。

## 构建入口与当时边界

`make openwrt-system` 从明确的固定原生构建输入组合系统。
常规构建与打包完成，实际config与实测版本逐字节相同；
重建kernel因timestamp/version不同，SHA-256为
`67716ef7f13b6f2f089b3fdcafe34937418026a984ee76c714c4b823d52a44f8`。
这个重建包及first-boot defaults没有作为新完整产物再次启动，
不能记录为另一次完整实测。

本次检查点尚未包含最终APK数据库登记、持久Docker、安装/恢复镜像与RDA STA/AP；
也不证明registry下载、一般Internet路由、IPv6或性能。
当时返回的是原低256 RAM router。后续APK、无线和安装结果见状态页，
这些后续结果不改变本次镜像的测量范围。
