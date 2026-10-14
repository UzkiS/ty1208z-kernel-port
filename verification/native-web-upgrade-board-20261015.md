# 原生网页升级与持久根重启实测（2026-10-15）

> 本页记录对应日期及精确镜像的验证结果；当前集成状态以 [STATUS](../STATUS.md) 为准。

2026-10-15，TY1208Z CA / Hi3798MV100、eMMC `008G30`、单核ARMv7。
官方OpenWrt固定 `58efa9917d4cc53fceed173529a286187649e827`，Linux6.12.112。
这是加入NTFS3之前的精确升级检查点，后续包见[USB报告](usb-storage-board-20261015.md)。

## 包身份

sysupgrade 131287242 B，SHA-256
`d13100b476e386276846454f4985841d7fb89717d79202223c5b17ecc7483fd8`。
kernel 4560012 B，SHA-256
`9c1ae8054e2e62251d10ee8cbef79287249bf69be5ab940a80441710408447d5`；
ABI `6.12.112~3ff30746f86cc6101046198a6e9bf330-r1`。
构建文件名保留UNTESTED，但这一个精确日常升级包已完成以下实测。
原厂RDA固件不公开。

## 官方网页升级

- 独立headless Chromium登录官方中文LuCI，上传精确镜像，核对SHA-256并选择保留配置。
- 官方sysupgrade停服务，stage2切RAM；串口显示p9根remount/unmount、
  staging挂载和冷读回前cache drop。
- 文件级后端核验新根、激活受管目录、写/读回p6，然后由官方流程重启。
- 只接收串口记录CA引导、1 GiB DDR、十一项allocation和默认eMMC启动，
  没有串口命令或持久boot设置变更。
- p9为1752576 × 4096 B、完整6846 MiB ext4 rw；
  p6/其他分区和SD只读，discard/WRITE_ZEROES队列上限零。
- 网络、LuCI、Passwall、Docker、无线、账号和key配置哈希相同。
  Docker启动追加的相同network列表项清理后字节也相同，有效规则不变。
  保留的root标记和Docker容器内容通过。
- Docker29.6.1、`/opt/docker`、overlayfs自动启动；
  预读与有界respawn避免慢存储下containerd冷加载超时。
- block-mount/lsblk存在；官方中文挂载页显示UUID配置与当前eMMC文件系统，
  未保存设置。正常启动回收旧staging并保留完成记录。

## 一次普通命令重启

升级后停止dockerd并sync，只执行一次正常reboot。
MMC保留仍挂载的gendisk，取得空闲PIO host，屏蔽IRQ并关闭时钟，无卡写入。
实际marker：
`EMMC_RO_SHUTDOWN_COMPLETE host-retained clock-disabled no-card-writes`，
以及已接受的SD/USB-host关闭marker。
新CA引导、十一项allocation、kernel和默认autoboot通过，无panic/ext4错误。
SSH返回后配置、完整p9、Docker自启和容器数据均保留；
无需人工断电或串口输入。

## 复用与限制

内存、网口、双代理核心、STA/AP、容器功能和time64复用未变组件证据。
新first-install全包没有再首刷；复用已接受流程及改变的内核/扩容/应用边界。
首刷1 GiB p9写约29分钟、读约11分钟，单扇区PIO仍是瓶颈。

该检查点包含SCSI/BLK_DEV_SD/USB_STORAGE及ext4/VFAT/exFAT，
当时尚未插外接USB盘。后续VFAT/NTFS3实测见USB报告。
SD写入/格式化、无线STA上联旁路由未验收，无线默认关闭。
CA fastboot、持久boot、其他eMMC分区、SD、boot0/boot1/RPMB和安全状态保持。

私有证据SHA-256：升级串口
`1cb2026fb3fef7ac8088dab864c5f26f9936db9424654f1505100487a8c3bd19`；
普通重启串口 `a3f986c2359836cc7298f2e95bc308f316aee09eb7501959d9487fd2ea319943`；
中文挂载页文本 `b6ae70a1b09d2a6d9800d08dde7722bd593406b5bff0427169ca73d0a3803a28`。
