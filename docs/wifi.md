# 板载 RDA5995 无线

本板使用USB `1e04:8888` RDA5995，无线不是Realtek。
当前系统已通过WPA2 STA、AP客户端及netifd角色切换；
无线默认关闭，完整结果和复用证据边界见
[无线实测](../verification/rda-wireless-board-20261014.md)与
[中文界面检查](../verification/luci-ui-board-20261014.md)。

硬件只有一个板载 radio。`2026.10.15` 曾因写死旧 USB 总线编号，
使官方自动探测器为同一芯片再生成 `mac80211` 项；该版公开下载已撤回。
`2026.10.15.1` 按芯片 USB 身份和实际 sysfs 路径配置，在自动探测前刷新路径，
只迁移同一硬件未修改且关闭的默认重复项，保留用户自定义配置和其他 USB 网卡。
验证范围见[修复记录](../verification/rda-radio-path-20261015.md)。

## 支持范围

单个AP或路由型STA，2.4 GHz，HT20/legacy，开放或WPA2-PSK/CCMP；
AP使用固定信道。不支持多接口、桥接STA、mesh、WPA3或TKIP。
STA上联再组合旁路由没有实测，不能由STA已联网推断。
station dump仍不完整，STA/AP同时运行和综合吞吐未验收。

最终模块完成STA DHCP/gateway、AP-ENABLED、AP退出再回STA；
真实手机AP认证/DHCP/页面访问复用较早模块的实测，
不能描述为最终模块又做了一次相同客户端测试。

## 来源、固件与模块

完整的 63 个驱动、构建及固件参考文件已纳入 [wifi/vendor/rdaw80211](../wifi/vendor/README.md)，
由本仓库维护。默认构建直接读取本地文件，不依赖上游网络或 CI 附件；
`make references-wifi` 校验并准备完整离线副本。原文件版权和许可证保留，
固定版本与哈希集中记录于 `reference/wifi-rda-usb.lock.json`。

完整系统默认包含 [firmware/rda5995](../firmware/rda5995/README.md) 中已在本板验证的
USB 运行固件，并按项目所有者授权随公开 Release 提供。
上游自带的 USB/SDIO `.hex` 参考也已保存；其 USB 文件与本板已验收版本不同，
不会在构建时自动替换运行固件。固件是给无线芯片加载的字节数据，不是 Linux 模块源码。
完整系统的驱动模块从本地源码编译，必须匹配本次 Linux 6.12 内核 ABI。

`wifi/overlay/` 维护新增代码，`wifi/replacements/` 维护协议函数替换，
`wifi/Kbuild` 维护共享对象列表。
`make wifi-usb-audit`、`make wifi-port` 分别检查单对象和完整模块；
原生APK入口见[打包说明](openwrt-wifi.md)。
使用原生Linux6.12 cfg80211，不能混用OpenWrt backports。

## 协议与生命周期修复

适配包含现代cfg80211/网络/文件API与64位boottime，
删除制造写入口和RF私有ioctl，WID打包拒绝eFuse写ID；
不让内核模块写持久MAC文件或启用测试固件。

实际控制解析检查头、长度、类型、WID、校验及响应ID，
限制错误重试与USB缓冲复制。密钥检查cipher/长度/索引/角色/peer，
修复短密钥越界、TKIP MIC、GTK sequence和错误传播。
扫描、扫描结果及关联IE在发布数据前检查完整边界及所有权。
USB TX padding扩展并清零尾部，保留逻辑skb长度与错误所有权。

芯片READY依赖实际固件状态/revision/version响应；
早期named-iovar未实现的阻碍和假成功已在历史报告中单独记录，
不能继续作为当前无线不可用的结论。没有真实命令的可选操作继续返回不支持。

角色切换由 `openwrt/system/wireless/rda.sh` 管理模块、固件和daemon；
显式insmod参数，记录前台wpad PID，子进程关闭序列化锁。
避免cfg80211持RTNL时USB重枚举。netifd发现器正确在EOF退出，
官方LuCI通过固定来源的检查式转换提供RDA选项。

相关实际函数的ASan/UBSan、ARM模块/APK及界面检查分别记录于
[验证索引](../verification/README.md)，不能以编译成功替代射频实测。
