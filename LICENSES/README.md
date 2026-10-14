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
- 可选RDA代码保留Rdamicro许可和模块GPL声明，代码从锁定来源本地获取。
  Wi-Fi构建不下载或重新分发厂商固件。
- 原设备固件、bootloader二进制、提取DTB、备份和含私有固件的完整镜像保持本地。

本地/CI诊断产物附带源码锁和补丁生成器；本项目当前没有公开的完整可安装二进制发布。

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
