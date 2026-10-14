# TTL、引导器检查与 RAM 开发工具

当前持久系统日常升级使用[官方网页流程](installation-plan.md)，无需重复RAM实验。
本页用于基线采集、故障检查或显式切换开发profile；串口名使用本机实际检测结果。
原始RX/TX和私有配置保存在被忽略的本地目录。

## 连接与依赖

使用3.3 V电平USB–TTL，核对板端GND/TX/RX，TX/RX交叉，
不猜针脚或接入未经确认的供电。不要同时用终端、HiTool和CLI占用串口。

```powershell
python -m venv .work/serial-venv
& ./.work/serial-venv/Scripts/python.exe -m pip install --require-hashes -r tools/requirements-serial.txt
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py list
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py capture --port SERIAL_PORT
```

Linux可使用相同Python入口及实际设备名。
正常boot采集应包含CA引导到当前系统的输出；SSH日志不是bootloader证据。
无输出时先核对接收、供电和当前内核身份，不反复盲目重启。

## 检查已经停止的引导器

设备停在空的 `fastboot#` 时：

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py inspect-current-bootloader --port SERIAL_PORT
```

工具回车确认身份后，只查询版本、help、ddrfree和环境；
遇Linux、外来版本或超时则停止，不加载镜像。
完整JSON及哈希匹配RX作为RAM规划输入。
较大内存profile还需紧邻受控重启的完整十一项allocation，
不能复用其他启动的地址记录。

## 受控 RAM 传输

`prepare_ram_boot.py` 检查镜像、DT/config、内存和解压范围；
`ram_boot_cli.py` 在发送前重新核对引导器版本、DDR及bootcmd。
以下只演示已准备且匹配的独立diag1，不是完整安装器：

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/ram_boot_cli.py --port SERIAL_PORT --artifacts artifacts/diag1 --inspection evidence/inspection.json --boot --capture-seconds 60
```

YMODEM/TFTP均要求filesize及设备CRC匹配才发送固定boot命令。
不带 `--boot` 只传输校验；`--boot-existing` 只适用于本次尚未重启、
同一镜像仍在RAM的情形，并重新校验CRC。
本板接受普通uImage的事实不代表其他镜像或引导器也接受。

## TFTP 与网络恢复

TFTP已实机完成kernel/initrd传输、设备CRC及原网络变量恢复，
并用于RAM切换与首次安装。
早期[离线记录](../verification/tftp-ram-offline-20261013.md)中的未验收仅指当时，
实机证据见[原生路由报告](../verification/openwrt-router-board-20261013.md)。

用 `--tftp-host-ip` 和 `--tftp-board-ip` 指定同一/24的不同本地地址，
设备地址应确认未占用。只读服务绑定指定电脑UDP/69，
给指定peer提供一至两个固定内存快照，不开放目录/上传，
不自动修改防火墙或启动常驻服务。

工具核对TFTP/setenv语法，保存网络变量、临时关闭autostart，
检查服务端完成、设备filesize和CRC；外部initrd独立校验。
最后恢复并读回原变量、停止服务后才启动，不调用saveenv或改持久boot。
串口失联时不向未知状态继续发送恢复或启动命令，
报告明确未恢复变量；后续操作前重新确认实际设备状态。

## 重启与诊断

优先使用与当前精确内核匹配、已经验收的正常重启和控制器关闭路径，
见[重启说明](restart.md)。旧diag1没有网络或硬件重启支持，
不能借用失效Hinas SSH会话或其他profile的reset能力。
持久系统普通reboot已验证，无需为日常操作手工切RAM。

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/board_diag_cli.py --port SERIAL_PORT
```

普通采集先核对精确diag1 release和提示符，再运行固定diag，
读取CPU、内存、中断、uptime、time64和dmesg；
不设置墙钟，文件探针只写RAM。外设profile显式选择对应采集身份。
日志与metadata绑定哈希，工具退出释放串口，不自动覆盖记录或重连。
