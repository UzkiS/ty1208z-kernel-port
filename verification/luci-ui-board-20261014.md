# 中文 LuCI 页面渲染检查（2026-10-14）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The current integrated read-only RAM OpenWrt serves working Chinese Dockerman
and RDA wireless configuration pages. This check used HTTP authentication and
Playwright Core with an isolated headless Chromium 155.0.8059.41 context at
1440 by 1000 pixels. It did not control the user's desktop/browser or use
computer-use. Credentials, session tokens, raw DOM/RPC output and screenshots
remain private.

An unauthenticated HTTP 403 carried `x-luci-login-required: yes` and the Chinese
login form; this was normal LuCI authentication, not loss of management.
Posting the existing root/empty-password login returned HTTP 200 and a session
cookie. Both authenticated routes reported `lang="zh-cn"`, no page JavaScript
errors and no HTTP responses with status 400 or higher during this check.

| Changed boundary | Observed result |
|---|---|
| Dockerman overview | Chinese navigation, summary tables and container/image/network/volume cards rendered. The live engine reported Docker 29.6.1, API 1.55, one CPU and 744.43 MiB RAM. |
| Docker service state | The restored RAM system initially had no running daemon; the UI correctly displayed a socket connection error. Starting the previously accepted RAM-only service made the overview display real engine data. |
| Wireless overview/editor | Disabled default radio and Chinese edit dialog rendered. Actual DOM options were AP/STA, 2.4 GHz, HT20/legacy, channels 1–13, open/WPA2-PSK and auto/CCMP. |
| WPA2 password dependency | Choosing WPA2 in the browser displayed the password input for both AP and STA. Changes stayed in the unsaved browser form; the dialog was closed without saving or applying. |
| Cleanup | The temporary Docker daemon stopped and its original UCI file was restored. `uci changes wireless` was empty, the default radio remained disabled, and both eMMC and SD whole-device read-only flags remained 1. SSH completed successfully. |

The primary desktop pages and dialogs were visually inspected. Dockerman's
upstream advanced environment table still contains long raw JSON values that
extend horizontally; this check does not claim responsive/mobile acceptance.
Docker action buttons and wireless activation were not exercised. Prior real
container and STA/AP evidence is reused rather than repeated. No storage writes,
reboots or installation occurred during this UI check.

| Private evidence | SHA-256 |
|---|---|
| Browser result | `0d0f3ca263191263fa5fb97dfcfbaa58dfad5ab879572443775f331bc94b0d42` |
| Docker viewport screenshot | `cb83e6bf29f74dff99cabc161c95a84099f8e0e486d382a07d326aee9fff8ec6` |
| Wireless editor screenshot | `bb80f4482b88e8da519c119549b6898f8cbf875cfbd67387aa22fa6f5c7930e7` |
| Wireless security screenshot | `06dca040197efe6242f18c0489f87abf0ccb3f9a71f4b1981ae7d7f7d58dbefd` |
| RAM Docker startup/RPC | `1fa74297965460caaf64ca55e1fc1b9f645bf1b16daf157ff9ec303e3430527a` |
| Cleanup/read-only state | `ce020b0f946a2c763716a1cea017316370818248b27d92e492a61ce072e4241e` |

Full p6/p9 installation, disk-root startup and configuration/Docker persistence
across reboot still require the pending separate installation authorization.
See the [prepared installation plan](../docs/installation-plan.md).
