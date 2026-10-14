# RDA5995 STA、AP 与角色切换实测（2026-10-14）

> 阶段记录：本页描述只读RAM系统的无线版本；当前持久系统见 [STATUS](../STATUS.md)。

单核原生OpenWrt RAM系统支持一个RDA5995 USB radio `1e04:8888`，
WPA2-PSK/CCMP STA或AP。本轮存储全程请求级只读。
固件来自私有原厂备份，固件、原始日志和网络凭据不公开。

| 边界 | 实际结果 |
|---|---|
| STA认证与数据 | 修正关联IE包含完整RSN；WPA2握手、无线DHCP、gateway ping通过 |
| 真实AP客户端 | 较早模块完成手机WPA2握手/DHCP，并从手机访问管理页；最终模块复用该证据，没有再做一次客户端试验 |
| 最终模块与netifd | STA DHCP和2/2 ping通过；STA→AP加载AP固件并到AP-ENABLED；退出AP停止注册的前台wpad、卸载模块；回STA再次DHCP/ping通过 |
| 有线管理恢复 | 加入无线脚本后handler discovery在EOF循环；串口恢复后仍可交互。修复循环、重启netifd恢复有线DHCP/SSH，非kernel lockup |
| 官方LuCI表单 | 检查式适配提供AP/STA、2.4 GHz、HT20/legacy、固定信道、开放/WPA2、auto/CCMP；实际modal builder配合form stub核对依赖和保存的psk2+ccmp。安装APK及minified JS匹配；后续headless浏览器检查中文概览/编辑和两角色密码框，未保存/应用；[UI报告](luci-ui-board-20261014.md) |
| 清理 | 删除临时STA/AP网络和私有测试设置；radio默认关闭，有线管理可达 |

最终未strip模块SHA-256：
`69a2dd20880ceb2a01f14602d6c990c8e4e93a0fb2de4f5076bda5a378788db1`；
安装的strip模块：
`77c7e37fa8b5834e7407088ab9755c151f6385d48fa961827a263f64c0696634`；
未变kernel：
`cc89e4a1d64706f2525aeb006a143ac8ca1d22e2c7d9445f7b1180583f17f05d`。

attach/teardown仅处理已初始化对象，并关闭不支持的P2P。
WID解码计入移除的wire length与关联固定字段；
AP GTK成功后先发布index再选default key。
USB TX padding扩分配、清零尾部，保留逻辑skb长度及错误所有权。
角色切换在用户空间退出module/daemon，避免cfg80211持RTNL时unregister USB。

后端显式 `insmod firmware_path=...`，因为ubox modprobe忽略附加参数；
登记前台daemon PID，子进程关闭序列化锁。
拒绝多接口、mesh、WPA3、TKIP及桥接STA。
station dump不完整，不作已验收能力。

改变的key/operation/USB padding实际函数ASan/UBSan通过，
未变关联IE复用前次sanitizer。
真实netifd handler通过JSON/空白/错误/EOF混合fixture：
`NETIFD_HANDLER_EOF_PASS`。
模块/原生APK、shellcheck、Ruff及源码语法通过，
没有为无线变更重复内存、Docker和代理压力测试。

| 私有回执 | SHA-256 |
|---|---|
| STA关联/握手/数据 | `8ab435180a6f5c3e7900c211f3907c8ac6c0cf2a83948a542baf3ac5ecbb7b98` |
| 手机AP客户端/页面 | `ed24da61e8c3763b44ff362b1c2dd8b1fb9ce297b7804e03f7dc6253f98cbf7c` |
| 较早netifd STA数据 | `34cb858851a8e4442ac1570e410389dc5c067b21360ae8f723dd7272ed7312b5` |
| 最终netifd AP启动 | `9591f31339106aa745ee7e444fdddc9dc866d06d3e05396eb60ca5859d3a95ba` |
| 最终AP退出/STA数据 | `8bcede39e1ca121631da9aa2c3c33c5be07ae0761c80bbd82064b50d24658cb7` |
| 清理及交付哈希 | `7608d2de86316c74114b0e6dff40079825157cf7e7fd6c8ecd4b5777d45d873b` |

最终RAM bootstrap22,987,418 B，supplement103,696,571 B。
离线APK事务选择174包，包括17项显式Docker/UI/无线要求；
107个匹配模块都有APK归属。最终后端、netifd EOF和LuCI修改均在包内。
八个交付文件（含两份kernel检查记录）复制并核对哈希。
这是复用组件证据、实测改变集成边界的RAM交付，
没有把离线重打包描述为另一次完整镜像启动或安装。
