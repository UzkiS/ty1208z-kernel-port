# TTL CLI：原系统记录、引导器检查与 RAM 诊断

SSH 基线、原 Hinas 启动、当前高安 fastboot 检查和 Linux 6.12 RAM 诊断均已完成。
本文记录各 CLI 的用途及前置条件；原系统记录仍可用于后续外设对照。

1. 使用 **3.3 V 电平**的 USB–TTL 串口，按此前成功使用的板端针脚连接 GND、
   TX、RX；TX/RX 交叉，不接适配器 VCC。未确认针脚时先核实，不能猜接。
2. 用下方 CLI 列出当前 COM 口，关闭占用同一端口的终端。HiTool 可作为原厂
   烧录工具保留，日常串口记录不依赖它。
3. 在下一次正常重启前启动 CLI，完整记录现有系统从引导器到 Hinas 登录提示的
   输出。保留原始日志在本仓库被忽略的 `evidence/` 中。
4. 首轮让原系统正常启动，记录 autoboot 提示、bootloader 版本、DRAM 声明、
   镜像校验信息、加载地址、设备树传递方式和早期内核内存信息。
5. 根据实际提示再安排进入当前 bootloader 的命令行。先核对只读帮助/环境查看
   能力，再选择具体命令；此文不假定支持 U-Boot、fastboot boot、TFTP 或 kexec。

## Windows PowerShell

在仓库根目录执行，Python 3.11 或更高。依赖安装在项目虚拟环境中，并校验哈希：

```powershell
python -m venv .work/serial-venv
& ./.work/serial-venv/Scripts/python.exe -m pip install --require-hashes -r tools/requirements-serial.txt
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py list
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py capture --port COM9
```

当前适配器为 COM9，不是固定配置；换 USB 接口后重新 `list`。默认参数是
**115200、8N1、无流控**。出现 `READY` 后才正常重启 Hinas，首轮不打断 autoboot。
程序只接收，不读取键盘、不向设备发送回车或命令，也不尝试自动重连。
打开串口前将 DTR/RTS 设为 false；设备连接仅使用 GND/TX/RX。

按 Ctrl+C 停止并释放端口。自动任务可使用一个尚不存在的停止文件：

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py capture --port COM5 --stop-file evidence/ttl-stop
# 在另一个终端停止接收；再次采集时换一个新的停止文件路径。
New-Item -ItemType File evidence/ttl-stop
```

也可用 `--duration 60` 限时接收。原始启动可能包含网络等待，完整采集建议不限时。
每次产生独立的 `evidence/ttl-cli-<UTC时间>` 文件：

- `.rx`：收到的原始字节，不修改编码或换行。
- `.txt`：UTF-8 可读副本，非法字节保留为转义表示。
- `.json`：端口参数、开始/结束时间、停止原因、字节数和原始数据 SHA-256。

数据实时落盘；屏幕输出会转义控制字符，避免设备输出触发宿主终端转义序列。
已有日志不会被覆盖；端口占用、USB 断开会报错，断开前的数据保留。日志默认只保存在
本地被 Git 忽略的 `evidence/`，公开研究说明前仍需脱敏。

Linux 下使用同一个脚本和依赖，将串口替换为实测的 `/dev/ttyUSB*`。
`make test-serial` 用 Linux 伪终端验证原始字节、分段 UTF-8、接收时零发送、
实时写盘、停止释放、端口冲突、断线、日志防覆盖及下述引导器检查协议，
不访问真实硬件。

## 引导器检查模式

`capture` 仍为只接收。新增 `inspect-bootloader` 是独立、限时的诊断模式：
看到本次 `Bootrom start` 或完整 DDR 初始化/训练/Starting fastboot 序列，
并确认已测量的 Fastboot 版本及 `Hi3798Mv100 (CA)` 后，
在内存分配表或 autoboot 提示处发送一次 Ctrl+C。只在收到行首的完整
`fastboot# ` 提示后，依次发送以下固定查询，每条都等待新的提示符：

```text
help
printenv bootcmd bootargs bootdelay loadaddr bootm_low bootm_size
help bootm
help tftp
help loadb
```

没有自定义命令入口。若身份不同、已进入 Linux、设备再次重启或等待超时，
立即停止，释放端口，不重试发送。默认总时限 180 秒，每次命令响应时限 10 秒。
日志额外提供 `.tx.jsonl`，记录尝试写入及驱动接受的字节；这不能证明板端收到。

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py inspect-bootloader --port COM5
```

须先出现 `READY` 才能安排正常重启；用户输入 `reboot` 后立即回复即可，
串口监听不依赖回复时机。旧 TTL 适配器上的两次检查未打断启动，查询命令
发送数为零；更换适配器后，COM9 的 CLI 已成功自动打断 bootdelay=0 的启动。
详情见
[检查记录](../verification/bootloader-inspection-20261012.md)。

已知成功的 CA fastboot 可以用 `tools/inspect_bootloader.py` 离线提取字符串；
脚本要求固定 SHA-256，输出仅保留在 `evidence/`，不会执行或刷入文件。
字符串中的命令名称也不能替代当前引导器的真实帮助输出。

## 接管已经停止的引导器

盒子已经停在空的 `fastboot#` 提示符时，无需再次重启。使用：

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py inspect-current-bootloader --port COM9
```

该模式只发回车，核对 Fastboot 版本，再读取 bootm/TFTP/YMODEM/Kermit/CRC32
帮助、ddrfree 和环境；不会打断启动、加载或启动镜像。检测到 Linux、版本
不同或响应超时则停止。其完整 `.json` 和哈希匹配的 `.rx` 是 RAM CLI 的输入。

## 已测量路径的 RAM 诊断

此路径针对当前已测量的 TY1208Z CA 引导器和诊断产物，不接受任意地址或命令。
`prepare_ram_boot.py` 校验镜像、附加 DTB、内核解压足迹和内存限制；
`ram_boot_cli.py` 在发送前再次核对当前版本、DDR 范围和 bootcmd。

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/ram_boot_cli.py --port COM9 --artifacts artifacts/diag1 --inspection evidence/ttl-cli-20261012T052211.866908Z.json --boot --capture-seconds 60
```

YMODEM 传入 DDR 后，只有盒子报告的大小和 CRC 都匹配才发送 bootm。
不带 `--boot` 时只传输和校验；`--boot-existing` 仅适用于已传入同一个镜像且
尚未重启的情形，仍须重新核对 RAM CRC。普通 unsigned uImage 已在本机
被接受，具体镜像及 shell 结果见 [实机报告](../verification/ram-boot-20261012.md)。
自动构建的其他镜像仍须逐个验证，不据此称为可刷固件。

进入诊断 shell 后可以运行固定诊断采集：

```powershell
& ./.work/serial-venv/Scripts/python.exe tools/board_diag_cli.py --port COM9
```

工具先核对诊断提示符和 exact kernel release，再运行 `diag`，读取 CPU、内存、
计时器/串口中断、uptime、time64 和 dmesg。不设墙钟；探针只操作 RAM `/tmp`。
较大的报告批量读取，避免网络目录逐字节写盘拖慢采集。所有模式均释放端口，
保留 RX 哈希与 TX 日志，不自动重连或覆盖已有记录。

本阶段无 eMMC/网络/USB 驱动；启动的是自身 initramfs。持久安装、原 Hinas
兼容性、外设和路由应用须独立验证，尚无刷写或安全状态修改命令。
