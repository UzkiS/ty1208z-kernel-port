# USB 存储与 NTFS 实机验收（2026-10-15）

> 本页记录对应日期及精确镜像的验证结果；当前集成状态以 [STATUS](../STATUS.md) 为准。

2026-10-15，TY1208Z CA / Hi3798MV100。
官方OpenWrt提交 `58efa9917d4cc53fceed173529a286187649e827`，Linux6.12.112。
当前系统汇总见[STATUS](../STATUS.md)。

## 设备与访问

USB2高速设备 `320a:827b`，容量122142464 × 512 =
62536941568 B（约58.2 GiB），可移除 `/dev/sda`；
大分区sda1为NTFS，sda2为32 MiB VFAT。
480 Mbit/s是枚举速率，不是吞吐实测。唯一编号、UUID、文件名和原始日志不公开。

前一内核已通过USB/block身份、VFAT `ro,nosuid,nodev,noexec` 挂载、
4 KiB文件读取/哈希和卸载，但NTFS缺少驱动。
新持久内核内置NTFS3及LZX/XPRESS，与全部模块、RDA模块和APK数据库共同构建，
未混入其他内核模块。

新内核实测NTFS3同样以只读选项挂载，读取非空文件前64 KiB并核对哈希后卸载。
整个USB盘的write-I/O与written-sector计数前后一致。
未格式化、改分区、修复、强制挂载或写USB；两分区均已卸载，
未保存自动挂载。USB写入/性能、exFAT和外接ext4未新增实测，SD继续请求级只读。

## 精确升级包

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| sysupgrade | 131399882 B | `38d42824f3189e24f079ec8693e334076736dce07fb8854c38e38079937544a2` |
| p6 kernel | 4677436 B | `3f16be94a64beb6ad8860bf84760ddb381fb7bfedaccefa13bfbae16ba2d621d` |
| 配套first-install | 132372681 B | `895305f7d0bf2200dbb3bb6b7641e5ae50136d770f3fd861add18e65ac2d4e76` |

ABI：`6.12.112~120d00c44db5befcdb6ed8d1f6825a56-r1`。
官方中文LuCI上传并核对精确哈希，保留配置后执行正常sysupgrade/stage2；
设备沿默认eMMC启动，无串口输入或人工断电。
只接收串口记录实际shutdown、CA引导、1 GiB DDR和完整十一项allocation。

根为p9 ext4 rw；p6/其他分区和SD仍只读。
配置、账号和key字节与私有备份相同，仅清理Docker启动追加的重复network列表。
Docker29.6.1从 `/opt/docker` 以overlayfs自动启动。
官方block-mount可为识别的ntfs选择ntfs3。

## 复用与限制

普通重启、容器内容、中文挂载页、内存、网口、双核心、STA/AP和time64复用未变组件证据，
没有重复整套功能矩阵。配套最新first-install全包没有再次首刷，
沿用已测首刷过程及变化的内核/升级边界。
原厂RDA固件和完整固件包仅本地私有交付。

私有升级串口证据SHA-256：
`db83a8a3beb986202a21faaebac99c50e08a8aaa455d7a9849dc7c3a2d368553`。
