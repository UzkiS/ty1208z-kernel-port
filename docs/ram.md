# 生产内存范围与历史低768验证

板上物理 DDR 为1 GiB。生产配置启用完整 `0x00000000–0x3fffffff` 地址范围，
同时启用 ARM32 HIGHMEM，取消上方整块256 MiB排除。低16 MiB与引导器实际11项
分配按精确范围保留；这些必要占用以及内核本身仍会从 MemTotal 中扣除。
新配置的构建和实机状态见[状态页](../STATUS.md)。
最小诊断及普通旧 router profile仍限制低256。
原引导器十一项分配从 `0x3e507000` 起，`ddrfree` 不扣除这些分配，
也不能建立完整安全内存图。

## ram768 profile

`make ram768` 生成单核独立诊断，关闭磁盘、网络、USB、模块、
highmem、PM和 watchdog设备服务。只使用实测 MV100 restart helper。
ARM 默认回收 init 页会暴露低16内页，因此这个精确 profile保留自己的 init 区；
不能把此配置随意扩展到其他板型。

RAM 规划同时要求紧邻受控重启的完整、哈希校验十一项 allocation，
以及新连接的引导器检查。CA/1GiB身份、地址或尺寸改变、记录过期均拒绝。
kernel、压缩数据和解压位置另行校验。

诊断在专用 `/tmp` tmpfs 创建512 MiB文件，
先要求至少700 MiB MemTotal和560 MiB可用，
完成地址相关及反相两种全量模式。
pagemap要求每页present、未swap、PFN在范围内，并至少256 MiB页位于256 MiB以上。
完成后清文件和挂载，不打开设备文件，不改墙钟。

[实机结果](../verification/ram768-board-20261014.md)：
763068 KiB MemTotal，512 MiB双模式与全部PFN通过；
76207页在256 MiB以上，清理、命令重启和原系统配置返回通过。
QEMU只验证通用 shell/time64及helper，不验证真实PFN图。

## 原生与系统组合

`make openwrt-router768` 使用独立身份、配置和 `router768` 构建树，
整合原生应用及网口，仍不启用存储/USB。
实机762296 KiB MemTotal、131072个PFN、双向64 MiB TCP、双代理核心、
命令重启和配置返回通过；
[原生记录](../verification/openwrt-router768-board-20261014.md)。

历史只读SD、eMMC及Docker系统曾沿用已测低768内存边界。
当前生产 DT 的 reservation 与完整 allocation 表逐项一致，不能把引导器仍在使用的
页面交给 Linux；本轮已通过四核并发 512 MiB 双模式和高于 768 MiB 的真实页面验证，
见[生产实测](../verification/production-profile-board-20261015.md)。
持久系统不需要每次串口人工启动；
上述新分配证据要求用于主动切换 RAM profile，
不能由旧记录放宽新的RAM加载范围。
