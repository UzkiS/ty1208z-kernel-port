# 下载与发布包

普通用户从 GitHub 的 [Releases](https://github.com/UzkiS/ty1208z-kernel-port/releases)
页面下载，不需要查找 CI 的短期构建附件。每个正式 Release 附带 `SHA256SUMS.txt`
和用途说明；校验通过后再使用对应文件。

后续完整固件默认生成 `bridge`、`hybrid`、`nat` 三版；见[网络版本说明](network-variants.md)。
新打包入口已实现，不表示三版已公开发布或完成实机验收，当前正式下载仍以下列版本为准。

当前正式版本为 [2026.10.15.5](https://github.com/UzkiS/ty1208z-kernel-port/releases/tag/v2026.10.15.5)，修复恢复默认按钮，并包含中文 ttyd 终端及配置页。
首刷用户同时下载 `first-install` 和 `install-ram` 两包；已安装用户只需 `sysupgrade`。
精确身份和上传核对见[发布记录](../verification/release-20261015.5.md)。
六个文件均已上传，GitHub SHA-256 和公开清单下载核对通过。
`2026.10.15` 因重复 radio、`.1` 因随机 MAC、`.2` 因缺少 ext4 恢复默认入口、`.3` 因缺少 ttyd LuCI 页、`.4` 因恢复默认按钮灰色撤回公开下载；已下载用户应使用本版。

文件用途固定如下：

- `ty1208z-ca-first-install-*.bin`：只用于 TTL/TFTP 临时 RAM 系统中的首次安装，不能
  在已安装系统上当作升级包。
- `ty1208z-ca-sysupgrade-*.bin`：已安装系统通过 LuCI“系统 → 备份与更新”或
  `/sbin/sysupgrade` 使用的日常升级包。
- `ty1208z-ca-install-ram-*.tar.gz`：首刷前临时系统所需的 `uImage`、bootstrap、补充
  用户空间和安装器，附独立中文说明、精确传输长度、CRC32 与内部 SHA-256 清单。
- `firmware/rda5995/` 中的固件：RDA5995 USB 无线所需的匹配固件，已随完整 Release
  打包；来源和哈希见目录 manifest。
- `wifi/vendor/rdaw80211/`：仓库内完整驱动与 USB/SDIO 固件参考，供离线构建和维护；
  完整系统使用已在本板验收的匹配 USB 运行固件。

CI 的普通运行仍会上传带 `HARDWARE-UNTESTED` 或 `QEMU-ONLY` 标记的短期附件，适合
开发者检查，保留期结束后会删除。CI 不会把每次 push 自动变成公开 Release；正式
Release 由维护者在完成构建、哈希核对和适用范围审查后创建并上传。
发布版本与资产身份由 Release 页面和 `release-manifest.json` 对应；只有页面实际存在
的资产才是已发布下载，源码提交或 CI 成功不等于上传完成。
当前已验收包的真实状态和限制见 [STATUS](../STATUS.md)。
