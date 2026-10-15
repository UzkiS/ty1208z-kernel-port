# 许可与第三方来源

本仓库按文件来源保留各自许可，不用单一许可覆盖所有内容。

- `overlay/` 的新增Linux板级/定时器/DTS文件和 `wifi/overlay/` helper按
  SPDX使用 **GPL-2.0-only**；生成Linux补丁保留上游许可。
- BusyBox `coreutils/stat.c` 使用 **GPL-2.0-or-later**，生成补丁遵循原许可。
  完整源码/许可从 `config/sources.lock.json` 固定归档取得。
- `tools/time64-probe.c`、项目自有Python/shell/构建/诊断/CI脚本、
  文档和配置使用 **MIT**，另有说明的除外；正式许可原文保留在下方。
- `wifi/replacements/` 的控制协议替换使用 **ISC**，与周围厂商源码一致，
  见 [ISC.txt](ISC.txt)。生成补丁保留Rdamicro许可声明。
- 厂商参考从固定公开SDK提交按逐文件哈希获取，保留GPL/Apache等原许可；
  下载内容不由本Git仓库重新分发。
- RDA 完整驱动与上游固件参考在 `wifi/vendor/rdaw80211/` 内维护，保留原文件的
  Rdamicro 等版权/许可和模块 GPL 声明；模块构建只使用其中的代码文件。已验证可用的 USB 固件按
  `firmware/rda5995/manifest.json` 单独维护，避免把不同总线或不同版本的固件混用。
- [高安 fastboot 归档](../bootloader/ty1208z-ca/README.md)保留原始二进制与来源压缩包，
  未取得对应源码或单独许可声明，不适用本项目的 MIT/GPL 授权。
  RDA5995 固件按项目所有者明确授权随公开 Release 发布，其他原设备固件、提取DTB、
  设备备份和未授权的完整镜像保持本地。
- DiskMan 固定于 `openwrt/storage/sources.lock.json`，使用 AGPL-3.0；来源生成器保留
  原版权，完整 LICENSE 随 APK 安装到 `/usr/share/licenses/luci-app-diskman/`。
  本板适配由 `tools/prepare_storage_packages.py` 和 `openwrt/storage/` 维护。

构建产物附带源码锁和补丁生成器；公开下载包见 [Releases](https://github.com/UzkiS/ty1208z-kernel-port/releases)。

## 项目自有脚本、文档和配置的 MIT 许可原文

Copyright (c) 2026 UzkiS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
