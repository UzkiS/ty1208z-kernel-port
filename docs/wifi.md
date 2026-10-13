# Wi-Fi 适配：本机为 RDA USB 方案

2026-10-12 的只读 SSH 基线确认机器存在 RDA USB 无线设备。当前 Hinas 没有
为它绑定驱动；现代内核也尚未集成对应驱动。Wi-Fi 仍是项目目标，扫描、联网
和 AP 模式需要分别验收。

用户要求板载无线也支持 AP 热点。当前源码包含 AP/beacon 和密钥回调，但主接口
的 AP-stop 命令路径仍未实现，现代内核下的固件启动和射频也尚未验收。后续 AP
验收必须覆盖 hostapd 启停、WPA2 加密、客户端连接与 DHCP、转发、断线重连及
重复启停；STA 与 AP 同时运行需要另外确认固件能力，不能由源码中的 AP 声明推断。

## 本机已确认

| 项目 | 运行时测量 |
|---|---|
| USB ID / 产品 | `1e04:8888`；RDA Microelectronics / RDA Wlan |
| 位置与总线 | USB 1-2，高速 USB；接口 0 为 FF/FF/FF |
| 完整接口 alias | `usb:v1E04p8888d0000dc00dsc00dp00icFFiscFFipFFin00` |
| 驱动绑定 | USB 设备级有通用 usb 驱动；**无线接口没有驱动绑定** |
| 无线网卡 | 当前没有；`/proc/net/wireless` 为空 |
| SDIO | 本次 sysfs 未暴露 SDIO 设备 |
| 已安装模块 | RTL8188EU/FU alias 均不匹配；当前内核模块目录扫描未找到 RDA 模块 |

这是 RDA USB 家族的硬件依据；精确型号、修订版仍需驱动查询或芯片丝印确认。
不能只凭 USB ID 就断言一定是 RDA5995。USB 已枚举说明设备可见，不能证明
射频、固件下载或 USB 数据传输已经工作。日志还有 bulk 端点 maxpacket 64
告警，后续适配需要检查。

## 原固件与公开源码线索

来源未确证的 Android 备份含 `rdawfmac.ko`，USB alias 匹配 `1e04:8888`，
依赖 cfg80211，vermagic 为 **`3.10.0_s40 SMP mod_unload ARMv7 p2v8`**。
备份也有 rda5995 USB code/data 固件，包括 AP、P2P、RF 文件。模块与固件的
匹配关系、对本机的适用性及固件分发许可未确认；ID 匹配不能确证整份备份
属于本机。3.10 模块不能直接装到当前 4.4 或诊断 6.12 内核。

主线 Linux 6.12 无线目录中未找到匹配 RDA 驱动。固定海思 SDK 的 Wi-Fi drv
子树也未找到 RDA 路径。公开的 OrangePi RDA 内核提供了另一条源码线索：

- 仓库：[orangepi-xunlong/OrangePiRDA_kernel](https://github.com/orangepi-xunlong/OrangePiRDA_kernel)。
- 审计固定版本：`0844fd6fb5851d644b7af8380975f425c64428e6`。
- 路径：`drivers/net/wireless/rdaw80211`；Kconfig 声明 `rdawfmac.ko` 与 USB 选项，
  `wland_defs.h` 定义 VID `0x1e04`、PID `0x8888`，`wland_usb.c` 使用这组 ID。
- 同一 Kconfig 依赖该平台的 RDACBDEV/I2C 电源控制；源码仍使用旧 cfg80211
  调用形式及 `init_timer`。USB 路径还需要审查固件下载和芯片 ID 判断。

这个 OrangePi 版本的 USB probe 对设备级描述符有额外限制，与本机 `dc00` 不符；
不能仅凭相同 VID/PID 选用它。它也尚未证明能驱动本机或完整移植到 6.12。
已检查文件的固定 URL/哈希见 [wifi-rda-audit.json](../reference/wifi-rda-audit.json)。
源码留在本地证据目录，不纳入最小诊断构建，也没有在盒子上加载旧模块。

## 独立 USB 编译审计

另一个公开版本来自 [realme TechLife Robot Vacuum 内核](https://github.com/realme-kernel-opensource/realme_TechLife_Robot_Vacuum-kernel-source)，
固定提交 `ef379d496bc0cd4b7bbeced783245f5e450a506d`，目录
`drivers/net/wireless/rdaw80211`。其 probe 接受本机设备级 `00`、接口级 `FF`
的描述符，并包含 WID 固件下载路径；这比单纯匹配 USB ID 更接近本机条件。

[来源锁](../reference/wifi-rda-usb.lock.json) 记录 63 个文件的固定 URL、长度和哈希。
`tools/fetch_wifi.py` 只下载 48 个代码文件，排除 `.hex` 固件，保留原许可头。
来源具备下载路径不等于固件版本、分发许可或芯片修订已经确认。

`make wifi-usb-audit` 已在本地 Linux 6.12.112 / ARM 工具链下成功编译
`wland_usb.o`。它使用独立配置和输出目录，覆盖厂商默认 SDIO 构建；
补丁仅更新 USB driver 注册结构及按接口 shutdown 回调。
该结果是 **USB 单个对象的编译验证**，没有链接完整 `rdawfmac.ko`，也没有
加载到盒子、下载固件、扫描或联网。CI 将重复此独立检查并校验生成补丁。

完整移植还需处理旧 cfg80211/定时器 API、平台供电、固件路径和芯片版本。
生产驱动不得启用或包含制造测试中的 eFuse 写入入口；这些接口须在模块集成前
审计并排除。当前最小诊断镜像仍没有 USB/Wi-Fi 驱动。

## 独立完整模块构建

`make wifi-port` 使用同一个固定 RDA 来源，但有单独的 API 补丁、配置和内核输出目录。
`wifi/overlay/` 只维护无线层新增文件，不能进入普通 Linux 板级 `overlay/`。
当前已在 Linux 6.12.112 下编译并链接完整 USB `rdawfmac.ko`，modpost 检查通过；
它不是已经能联网的驱动，也没有加载到本机。模块只能匹配相应配置/版本的内核。

本次适配覆盖 kernel_read/文件读取、随机数、unaligned include、网络地址/接收/超时
回调、cfg80211 的 link 参数、管理帧注册、AP beacon/stop 回调和漫游通知。
boottime 使用 64 位 ktime 和 ARM 内核的 div_u64，不引入 32 位 timespec 或
无法链接的用户空间除法辅助函数。厂商现有定时器兼容分支可在 6.12 编译。

生产边界包括：

- 删除 eFuse 写函数和 RF 私有命令解析器，拒绝 Android/RF 私有 ioctl；
  普通扫描、STA/AP/P2P 使用 cfg80211 路径，私有厂商工具不受支持。
- 普通/批量 WID 打包同时拒绝三个 eFuse 写 ID，保留校准信息读取。
  `WLAND_POWER_EFUSE` 的读取后 RAM RF 设置不是 eFuse 烧写。
- 删除测试文件触发、RF 固件分支和可变 test-mode 状态；只接受精确的 sta/ap/p2p 模式。
- 文件写辅助函数返回不支持，由用户空间管理持久配置；模块不写 `/etc/WLANMAC`。
- 修复短 WEP/CCMP 密钥被无条件按 32 字节读取、TKIP MIC 布局、GTK sequence 边界，
  并传播固件加密密钥设置失败。删除调试前的漫游 BSS 引用释放，交给 cfg80211 消费。
- 独立完整模块配置关闭 debugfs；符号/ELF/vermagic/USB alias 检查拒绝残留制造写函数。

`test_wifi_port.py` 在 ASan/UBSan 下执行实际 WID 打包函数与新增密钥处理代码，
验证 eFuse 写入在改动消息前被拒绝、合法查询/普通请求继续打包、短密钥没有越界，
TKIP MIC 顺序和错误长度处理正确。它也检查制造入口/固件路径/漫游引用的源码边界。
这些是软件回归，不是射频或联网证据。

控制协议后续修复维护在 `wifi/replacements/`，通过锁定来源的函数替换生成补丁。
WID 解析先检查头部/数据长度，再读取数据；修正 SHORT 的两字节长度，二进制字段
检查校验和。响应同时核对传输长度、两层协议长度、类型、WID 和实际数据范围。
接收完成函数限制丢弃消息 ID 不匹配响应的次数，先检查长度再读取 ID；USB 目的
缓冲区不足时拒绝整个响应，RX 分发也在复制前核对源帧与控制缓冲区容量。
`test_wifi_control.py` 在 ASan/UBSan 下执行实际补丁后的解析、完成等待和 USB 接收
函数，验证所有有效类型的精确短前缀、错误尺寸/校验、截断/不匹配响应、ID 回绕、
等待上限与超长 USB 响应。具体身份和限制见
[控制协议回归](../verification/wifi-control-20261012.md)。这不覆盖全部数据帧或射频行为。

密钥回调现已在日志和固件请求前校验 cipher/长度、索引、序列号、角色及 peer/BSSID，
避免空密钥、错误字段或未支持角色报告成功。可选 AP-reset 分支仅在固件确认成功后
更新缓存 GTK 长度；当前 USB 构建没有启用该分支。新增回归执行实际 cfg80211/PTK/GTK
函数，核对 WID、报文字段、MIC/RSC 和固件错误传播，完整模块重新链接通过。
密钥回调范围见 [密钥回调报告](../verification/wifi-keys-20261013.md)。BIP/WAPI
管理密钥没有已验证的命令路径，不能当作普通 GTK 写入；它们已从 cipher 能力声明移除。

尚需确认的硬件/功能包括现代内核 USB host/PHY、准确芯片 revision、对应固件、
供电/冷启动、扫描、加密关联、DHCP、吞吐、断线恢复和 AP。
公开来源中的其他旧逻辑（例如部分 key deletion/AP stop 实现）仍需行为审查及实测，
不能用成功链接替代这些验证。固件未下载、未打包，分发许可仍未确证。
旧 `wland_fil_iovar_data_set/get` 的 transport 实际被禁用，却返回成功；移植版本现明确
返回不支持，保留 caller 缓冲区。删除/读取密钥和默认密钥选择同样不再报告空操作成功。
已有的第二接口 AP-stop 命令仅在固件确认成功后改变状态；主接口没有实现的停止路径
明确返回不支持。失败的 TX-power 请求不更新缓存，读取错误日志不读未赋值输出。
这些修正可能暴露旧初始化/可选功能中原来隐藏的失败，部分忽略错误的 caller 仍待审查。
它们不代表上述功能已实现；最新模块身份、实际函数测试及限制见
[操作回归报告](../verification/wifi-operations-20261013.md)。

实际 USB 编译分支已经确认：网卡启动必经的漫游配置和 band 更新依赖这些未实现的
named-iovar 请求，当前模块因此仍不能正常启用无线接口。初始化失败现会撤销 READY，
避免后续回调误认为接口可用；真实 helper 和 cfg80211-up 回归已重现该阻碍。
源码选择的 `WLAND_VER_91_H` 不是本机 revision 测量，不能据此配固件或虚构能力回复。
完整路径、测试范围和最新模块身份见
[启动报告](../verification/wifi-startup-20261013.md)。

定向扫描现在在首个固件请求失败或完成等待超时时停止，不再由后续 SSID 的
成功结果覆盖错误。等待标志在请求前发布，避免快速完成事件被随后覆盖；
请求的 SSID 数量和长度先校验。实际函数的 ASan/UBSan 与完整模块重新链接
通过，身份与测试范围见 [扫描报告](../verification/wifi-scan-20261013.md)。
这尚未覆盖扫描结果解析、完整异步并发或实机射频，初始化缺少传输的阻碍仍存在。

扫描结果解析已另外加入实际接收长度、消息/WID 与逐个 IE 的边界检查；完整
32 字节 SSID 不再额外写终止符，扩展速率连续追加并限制数量。结果被丢弃或
分配失败时释放临时 IE，插入/替换成功后明确转交给扫描列表。真实解析器和
事件回调的 ASan/UBSan、完整 ARM 模块链接与核心回归通过，见
[扫描结果报告](../verification/wifi-scan-results-20261013.md)。异步 teardown、
其他关联/计划扫描解析及固件/射频仍需独立验收；初始化传输阻碍尚未解除。

STA 响应/AP 请求共用的关联帧解析现先检查实际 MAC/可选 HT 头、固定字段和所有 IE，
再分配及发布数据。短帧与长度相减不再导致越界；失败保留已有 IE，新站点分配失败
释放临时副本，替换请求清除过期的 WMM/HT 标志。实际原始函数在同一短帧回归中触发
ASan 越界，修正版在独立模块和原生包源码上均通过，完整 ARM 模块、APK/ABI 与损坏包
检查通过，见 [关联帧报告](../verification/wifi-association-frames-20261013.md)。其他
关联查询、AP 连接事件、并发 teardown 和实机 STA/AP 仍需验证。

## 后续实施顺序

芯片启动现在要求固件状态、revision 和固件版本查询返回实际数据后才发布
`chip_ready`；失败不再伪造 u04 或成功状态。实际 getter/解析器/启动函数的
错误回复、重试和字符串边界已通过 sanitizer，完整模块和原生 APK 已重编译，
见 [启动查询验收](../verification/wifi-chip-start-20261013.md)。这仍未解决
cfg80211 的 named roaming/capability 初始化，也未证明实机无线可用。

可选的 [原生 OpenWrt 打包入口](openwrt-wifi.md) 复用同一驱动补丁和
`wifi/Kbuild`，在独立目录使用原生 Linux 6.12 cfg80211，不混用 backports。
实际 APK 的模块、内核 ABI、自动加载与固件边界单独检查；编译/打包结果
不表示板载 Wi-Fi 已联网。

1. 先让现代内核最小串口/计时诊断在实机启动，再适配 USB 控制器、PHY、时钟、
   复位和供电，确认现代内核也能稳定枚举这个设备。
2. 独立审计 RDA 源码、固件协议与许可，核对芯片版本。把平台电源依赖和 Android
   路径同 TY1208Z 板级支持分开，评估旧 cfg80211/定时器接口的移植成本。
3. 建立匹配目标内核的可选驱动构建；先验证 USB/固件初始化、扫描，再验证加密
   联网、DHCP、DNS、收发、断线重连与冷启动。AP 和 Passwall 路径单独验证。

找不到可用 RDA 驱动时，应报告具体阻碍并继续源码研究；不能把 Realtek 驱动
当成板载 Wi-Fi 的实现。内核版本升级本身不会补出 RDA 驱动。

## Realtek 离线线索与可选 USB 网卡

本地 Hinas 包及当前系统都有匹配旧 4.4 内核的 RTL8188EU/FU 模块；它们属于
其他 USB 设备，不对应本机板载 RDA。若以后另接支持的 USB 网卡，可单独评估：

| 设备 | USB ID | Linux 6.12 驱动 | 固件 |
|---|---|---|---|
| RTL8188EU | `0bda:8179`、`0bda:0179`、`07b8:8179` | rtl8xxxu / 8188e | `rtlwifi/rtl8188eufw.bin` |
| RTL8188FU | `0bda:f179`，厂商接口 | rtl8xxxu / 8188f | `rtlwifi/rtl8188fufw.bin` |

需核对完整接口描述。所查 8188f 子驱动声明 AP 支持，8188e 没有同样声明；
它们也要实机验收。更换网卡不是当前板载 RDA 适配的完成条件。
