# 系统重启与控制器关闭

当前持久系统已通过普通命令重启并沿原有 eMMC p6 路径自动启动。
磁盘根的 MMC shutdown修复及实际记录见
[网页升级与重启报告](../verification/native-web-upgrade-board-20261015.md)。
这里同时保留早期独立 RAM 重启流程，不能将其“未验收”结论套用到当前系统。

## 实测 MV100 路径

本板 WDG0位于 `0xf8a2c000`。实际 AMBA ID cells读零；
原Hinas/SDK用 DT覆盖ID注册 SP805，不能当作真实ID测量。
可用的窄范围 helper同时核对 SYSID0 `0x37980100`、
零ID、CONTROL禁用、LOAD/VALUE `0xffffffff`、RIS/MIS/LOCK零。
probe只读，显式 restart回调再次检查后才执行 unlock、禁用control、
短load和reset control四次写及flush。不提供watchdog服务或安全状态写入。

原生RAM模块由 `tools/build_openwrt_restart_module.py` 对精确
config/zImage/符号/编译器/libc检查后构建，验证ARM ELF/vermagic，
不会自行加载。临时模块只适用于对应内核，不能带到其他profile。

## RAM 切换流程

`board_restart_cli.py` 独占串口，先核对内核、源码revision、
live DT、实际绑定与注册，再发一次正常重启。
新CA引导出现后截停并重新检查，重新传输精确kernel/initrd、核对双CRC和恢复配置。
不能因命令已发出推断成功，不自动重试reset。
[早期原生实测](../verification/native-restart-board-20261013.md)已经通过自动返回。

SD识别/只读、eMMC只读和系统profile必须分别确认请求停止、
IRQ屏蔽和PIO时钟关闭，才允许重启。
磁盘根仍挂载时保留gendisk，避免 `del_gendisk` 等待阻塞；
host空闲后停止控制器。SD/eMMC实际返回证据分别在
[SD报告](../verification/sd-ro-board-20261013.md)和
[eMMC报告](../verification/emmc-ro-board-20261014.md)。

## 保留的严格 SP805-ID 实验

`make restart` 仍生成原始 `restart1` 独立候选，
要求真实peripheral ID `0x00141805`（24位mask）、cell ID `0xb105f00d`
和CONTROL零。这个严格身份不符合本板实际零ID，因此没有实机重启验收，
不因后来MV100 helper可用而放宽它。

其[离线报告](../verification/restart-offline-20261012.md)只证明构建、
实际helper sanitizer、DT/config/layout、PTY及通用QEMU。
串口采集/重启工具必须使用匹配profile和实际串口：
`board_diag_cli.py --port SERIAL_PORT --profile restart1`、
`board_restart_cli.py --port SERIAL_PORT`。
诊断PID1是RAM shell，因此该独立工具使用固定 `reboot -f`；
正常OpenWrt系统应走正常服务关闭流程。
