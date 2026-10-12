# 现有 Hinas 的只读 SSH 基线

`tools/collect-baseline.sh` 经 SSH 标准输入运行，不在盒子上保存脚本或报告。
内容包括当前内核/用户空间、内存/中断、分区、USB/SDIO ID、Wi-Fi 驱动线索、
运行设备树和内核日志。不安装软件、不加载模块、不修改分区或时间、不重启。

在本机交互式 PowerShell 使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\collect-baseline.ps1 -TargetHost <box-ip>
```

用户名默认 root，端口默认 22；需要时使用 `-LoginUser` 和 `-Port`。
密码由 SSH 在本机终端提示，不写入脚本。Linux 可直接使用：

```sh
mkdir -p evidence
ssh root@<box-ip> 'sh -s' < tools/collect-baseline.sh > evidence/ssh-baseline.txt
```

Windows wrapper 保存报告到被 Git 忽略的 `evidence/ssh-baseline-日期.txt`。
原始报告可能含 MAC、网络地址、挂载路径及 DTB；保持本地，发布时仅提交
匿名化的硬件事实和验证结果。某个可选命令缺失会保留提示，不自动安装工具。

SSH 基线不能证明安全启动状态或 bootloader 命令可用性。加载候选前还需要
正常启动的 TTL 日志和经过核实的内存/临时加载条件。

## 采集状态与 Windows 换行

成功报告必须包含独立行的 BEGIN、END 标记，且 SSH 退出码为 0。
首次 Windows 采集虽然返回 127，但完整报告已到达 END；本机复现显示 PowerShell
向原生程序管道追加了 CRLF，末尾的 CR 被 `sh -s` 当作额外命令。
脚本已明确 `exit 0`，并在 `make lint` 中回归 LF 与追加 CRLF 两种输入。
报告末尾已完整时应先审阅现有数据，避免无意义地重复密码登录。

虚拟网卡不读取 speed/duplex；其他不可读取的可选 sysfs 属性在报告中保留
`[read unavailable: ...]` 提示。命令缺失或属性不支持不代表 SSH 认证失败。

2026-10-12 的匿名化结果见 [基线记录](../verification/baseline-20261012.md)。
下一阶段的串口记录步骤见 [ttl-baseline.md](ttl-baseline.md)。
