# 干净构建 CI 修复与结果（2026-10-15）

安装系统的实机验收与干净源码构建分别记录，当前功能见 [STATUS](../STATUS.md)。

## 已修复的构建边界

- `40cd3f0` 的实际eMMC driver harness缺少新持久shutdown的stub。
  已补齐并验证idle host保留、IRQ/clock写入和active/missing-host拒绝，
  原只读检查保留；实际函数ASan/UBSan通过。
- 新system Kconfig选项使独立应用变体的syncconfig询问。
  应用fragment已显式关闭该opt-in，SD/eMMC实际配置的olddefconfig和闭合stdin检查通过。
- 组合QEMU根变大，初始tmpfs配额不足；ramfs展开后整根再复制又超过768 MiB。
  386217472 B合成fixture在旧路径复现全局OOM杀cp；
  新QEMU专用入口逐文件复制/删除到90%配额tmpfs，再启动原生
  `/sbin/init`/procd。相同fixture可达shell且无全局OOM。
  原归档和 `/init` 不改，但fixture不再执行旧 `/init` 的整根复制。
  未添加磁盘/主机网络、删减成功marker或放宽实际内存要求。
- SD干净构建进一步暴露 `CONFIG_TY1208Z_ROUTER_EMMC_RO` 缺省项。
  主target fragment现显式关闭它，专用eMMC fragment仍单独选择。
  实际Linux Kconfig的缺省版本在listnewconfig列出该项；
  修复版本无此新项，闭合stdin的syncconfig返回0。
  该配置改动不改变已经接受的运行镜像。

## 实际运行记录

| 检查 | 提交 / run | 当前结果 |
|---|---|---|
| 完整诊断 | `559c2d8` / [38642766702](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38642766702) | 成功，包括实际eMMC shutdown harness及后续独立profile |
| 应用矩阵原运行 | `5bba089` / [38639747752](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38639747752) | eMMC应用已成功；普通应用/路由仍在构建；SD因上述配置项失败，router768构建机失联 |
| 修复后的SD单项 | `32cab4a` / [38650502790](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38650502790) | 已启动，待实际结果 |
| router768单项重跑 | `32cab4a` / [38650507793](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38650507793) | 已提交，待实际结果 |
| Docker/fw4/双核心组合 | `086df54` / [38641050654](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38641050654) | 仍在构建，待实际结果 |

router768失联由GitHub check annotation明确记录，发生在toolchain完成前，
没有可用编译错误或产物，不能报告为源码失败或成功。
保留其他正在运行的任务；新增手动target选择只重跑所需profile，
默认push/PR仍保留完整五项矩阵。

配置/工作流提交跳过自动广泛触发，随后明确派发上述两个精确提交的单项构建；
跳过自动触发不构成通过证据。未变化组件复用既有验收，
未为了CI修复重复设备安装、内存、无线或应用实机测试。

此前组合构建还遇到BusyBox HTTPS下载超时，发生在编译/运行前；
后续由修复内存交接的运行替代。重复、无变化的任务取消记录不作成功计数。
