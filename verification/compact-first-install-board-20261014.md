# 紧凑 RAM 网页首刷实测（2026-10-14，更新于2026-10-15）

> 本页记录首刷和后续修复的精确检查点；当前集成状态见 [STATUS](../STATUS.md)。

设备为TY1208Z CA / Hi3798MV100、eMMC `008G30`、物理DDR1 GiB。
旧完整p9 writer在5,149,818,880 B处停止，flush并锁回只读，
尚未写p6，自动续跑已停；没有启动该不完整根。

## 紧凑安装与失败恢复

真实中文LuCI上传/哈希确认、官方sysupgrade、RAM pivot、
1 GiB p9写入/完整SHA-256读回、配置恢复、p6写入/读回/锁定均通过。
现有CA引导器从eMMC读入安装内核、验证CRC，进入真实p9 ext4 rw根。
p9写入约29分钟、完整读回约11分钟，底层仍为单扇区PIO。

首次stage2缺少tr，失败返回upgraded后触发重启；
串口截停并通过双CRC校验TFTP恢复同一RAM系统和配置。
首刷和日常后端现都复制tr，失败保留RAM串口恢复shell，
tmpfs pre-upgrade hook保留官方配置备份选择。

## 在线扩容与冷启动

resize2fs最初O_RDWR打开已挂载块设备，被raw-write保护拒绝；
MMC队列还错误宣告基于erase的zeroout，而CMD35/36/38禁止。
修复后挂载检查用O_RDONLY和挂载点ioctl，
核对 `/dev/root` 指向p9，不再宣告discard/WRITE_ZEROES。

冷启动实际从262144扩至1752576个4096 B block，
完整6846 MiB p9，文件系统约6.5 GiB、当时可用约6.2 GiB。
配置哈希、Docker容器标记、Docker29.6.1自动启动和中文Dockerman通过。
持久engine使用containerd overlayfs snapshotter，早期RAM suite的overlay2不描述此engine。
慢速containerd加载超过Docker15秒deadline，原生APK增加注册procd前预读及有界respawn。

## 普通重启修复与包身份

首次普通磁盘根reboot因 `del_gendisk` 等待仍挂载的根而阻塞，
一次人工断电恢复已安装系统。
修复保留persistent MMC host/card，核对PIO空闲后关闭IRQ/时钟，无卡写入。
精确新日常升级包和一次普通reboot已实测通过，
无需UART输入；[升级报告](native-web-upgrade-board-20261015.md)记录
新CA/1 GiB/十一项allocation和shutdown。

NTFS3加入前的首刷包为132260041 B，SHA-256
`9ab558d6ca8a86082efde96154fd867125da02ea9cb1af2f56f892f102d13ad7`；
kernel4560012 B，SHA-256
`9c1ae8054e2e62251d10ee8cbef79287249bf69be5ab940a80441710408447d5`，
ABI `6.12.112~3ff30746f86cc6101046198a6e9bf330-r1`。
该次重新打包的完整首刷产物没有再覆盖首刷，复用流程与变化边界证据。

最新NTFS3首刷包和精确内核见[USB报告](usb-storage-board-20261015.md)；
同样未再次全包首刷，变化的kernel通过日常升级和真实NTFS读取验证。
原RDA固件、串口、备份与回执保持私有。
SD、CA fastboot、持久boot环境、其他eMMC分区和boot0/boot1/RPMB不是安装目标。
未重复未变化的内存和应用完整测试。
