# RDA5995 固件

这些二进制来自当前 TY1208Z CA 实机原系统备份，适配 USB `1e04:8888` 的 RDA5995。
它们随明确授权的完整 Release 包发布，文件身份见 [manifest.json](manifest.json)。
来源仍是用户提供的设备备份；未声称这些二进制是本项目原创或由上游源码重新编译。

完整驱动与上游固件参考保存在 [wifi/vendor/rdaw80211](../../wifi/vendor/README.md)，
固定文件身份见 `reference/wifi-rda-usb.lock.json`。上游 USB HEX 与这里已验收的运行版本
不同，完整系统默认使用本目录中的五个二进制；打包前检查 manifest 中的大小和哈希。
不同 RDA 型号、板型或固件版本不能仅凭 USB ID 判断兼容。
