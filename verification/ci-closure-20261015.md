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
| 应用矩阵原运行 | `5bba089` / [38639747752](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38639747752) | 普通应用、路由、eMMC 成功；SD 因上述配置项失败，router768 构建机失联；原矩阵整体失败 |
| 修复后的SD单项 | `32cab4a` / [38650502790](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38650502790) | 成功 |
| router768单项重跑 | `32cab4a` / [38650507793](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38650507793) | 成功 |
| Docker/fw4/双核心组合 | `086df54` / [38641050654](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38641050654) | 成功；尚不包含随后加入的 DiskMan |

router768失联由GitHub check annotation明确记录，发生在toolchain完成前，
没有可用编译错误或产物，不能报告为源码失败或成功。
保留其他正在运行的任务；新增手动target选择只重跑所需profile，
默认push/PR仍保留完整五项矩阵。

配置/工作流提交跳过自动广泛触发，随后明确派发上述两个精确提交的单项构建；
跳过自动触发不构成通过证据。未变化组件复用既有验收，
未为了CI修复重复设备安装、内存、无线或应用实机测试。

此前组合构建还遇到BusyBox HTTPS下载超时，发生在编译/运行前；
后续由修复内存交接的运行替代。重复、无变化的任务取消记录不作成功计数。

## 生产配置发布提交的新增运行

`5f3b863` 包含四核、完整内存、普通存储读写、DiskMan、仓库内 RDA 文件及公开构建路径处理。
`8be787a1e97631818c637bbd98de3e625270dc71` 仅进一步更正生产报告中的模块字节数，
两次提交均跳过自动广泛触发，随后在该精确提交上显式派发以下检查：

| 检查 | run | 派发后的状态 |
|---|---|---|
| 完整诊断及 time64 回归 | [38673515248](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38673515248) | 失败：旧只读 eMMC driver harness 缺少新配置宏定义，见下文 |
| Docker/fw4/Passwall/DiskMan 组合构建与 QEMU | [38673519682](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38673519682) | 运行中，尚未取得完成结论 |

以上两项均于 2026-10-15 02:55 UTC 派发。表格已更新诊断失败结论，组合构建仍在运行；后续结果以对应 run 页面为准，
不把旧提交的成功结果算作本提交通过。最终源码本地 `make lint` 已通过；补装固定哈希的
pyserial 后，`make test-serial` 的七组共 93 项测试全部通过，该目标不操作真实硬件。
生产内核编译、实际策略 sanitizer、真实升级和变化应用组件的实机结果见
[生产报告](production-profile-board-20261015.md)，与上述远端干净构建分开记录。

诊断 run 的 `test_emmc_ro_driver.py` 使用自行定义的 `IS_ENABLED`，缺少
`CONFIG_HI3798MV100_EMMC_WRITE` 后无法编译实际 probe/shutdown 函数。
已将该宏绑定到 harness 原有的安装模式变量，分别验证原只读 host 移除和持久写入 host 保留分支，
实际 Linux 源码的 ASan/UBSan 检查通过；内核驱动和二进制不变。修复提交将显式重跑诊断 CI。
