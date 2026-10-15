# RDA 驱动与固件本地维护

`rdaw80211/` 保存完整的 63 个固定版本文件：48 个驱动/构建文件和 15 个固件/配置参考。
默认构建直接校验并复制这里的文件，不访问网络。`make references-wifi` 可准备离线构建输入；
显式使用 `tools/fetch_wifi.py --download-upstream --output <目录>` 才会下载上游作比对。

原始文件按字节保存，包含上游的版权和许可声明；[来源锁](../../reference/wifi-rda-usb.lock.json)
记录固定提交、完整路径和哈希。源码基于 realme 公开内核的
`ef379d496bc0cd4b7bbeced783245f5e450a506d`，目录为 `drivers/net/wireless/rdaw80211`。
代码中的 Rdamicro ISC 等声明与模块 GPL 声明照常保留，许可原文见 [LICENSES](../../LICENSES/README.md)。

Linux 6.12 适配维护于 `wifi/overlay/`、`wifi/replacements/` 和补丁生成器，
生成补丁应用到独立构建副本；需要更新原始基线时同时更新来源锁。
`.hex` 是逗号分隔的十六进制字节参考，并非固件的可编译源码。
当前实机验收使用的 USB 运行固件保存在 [firmware/rda5995](../../firmware/rda5995/README.md)，
完整系统默认打包这份匹配固件；SDIO、RF 测试及其他版本文件不自动替换运行固件。
