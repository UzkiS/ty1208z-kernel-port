# 用 CLI 记录原系统的 TTL 启动

SSH 已完成 Linux 运行时信息采集。现在需要看到现有高安 fastboot 的启动输出、
内存声明和命令能力，才能决定诊断内核如何临时加载。本阶段先记录原系统启动。

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
& ./.work/serial-venv/Scripts/python.exe tools/serial_cli.py capture --port COM5
```

COM5 是此次本地识别结果，不是固定配置；换 USB 接口后重新 `list`。默认参数是
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
实时写盘、停止释放、端口冲突、断线和日志防覆盖，不访问真实硬件。

## 采集之后

待核查的是 RAM 加载/启动命令、验签要求、bootloader 占用及安全保留区域、
候选输入与解压位置是否重叠。尚不运行加载、擦除、刷写、环境保存或安全状态
修改命令。原系统能接受某个镜像，不能证明普通未签名候选一定能启动。

确认这些条件后，才校正诊断设备树和镜像包装，生成明确可审阅的临时启动步骤。
第一个候选只启动自身 initramfs，后续 eMMC 与 Hinas 兼容验证另作阶段。
