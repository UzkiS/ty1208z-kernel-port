# Licenses and sources

This repository is not relicensed under a single blanket license.

- New Linux board/timer/DTS files in `overlay/` and wireless helpers in
  `wifi/overlay/` use **GPL-2.0-only**, as stated by
  their SPDX headers. Generated Linux patches retain upstream licensing.
- BusyBox's `coreutils/stat.c` declares **GPL-2.0-or-later**. Its generated patch
  follows that licensing. The complete BusyBox source/license is obtained from
  the pinned archive in `config/sources.lock.json`.
- `tools/time64-probe.c` uses **MIT**. Other project Python/shell/build scripts,
  diagnostic shell scripts and CI files use **MIT**, with the license text below.
- Project documentation and configuration use **MIT** unless otherwise marked.
- Project control-protocol replacements in `wifi/replacements/` use **ISC**,
  matching the surrounding vendor source; see [ISC.txt](ISC.txt). Generated
  patches retain the original Rdamicro permission notices.
- Vendor references are fetched from a pinned public SDK commit with per-file
  hashes. They keep their original licenses (including GPL and Apache notices).
  Downloaded reference files are not redistributed by this Git repository.
- Original device firmware, bootloader binaries and extracted DTBs remain local.
- Optional RDA source files retain their Rdamicro permission notices and module
  GPL declaration. Checked patches preserve those notices; the locked original
  code is fetched locally rather than vendored. No vendor firmware is fetched
  or redistributed by the Wi-Fi build.

Upstream source locks and patch generators ship with each local/CI diagnostic
artifact. No ready-to-install binary release is published by this project.

## MIT license for project-owned scripts/docs/configuration

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
