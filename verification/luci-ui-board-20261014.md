# 中文 LuCI 页面渲染检查（2026-10-14）

> 阶段记录：本次使用只读RAM系统；当前持久系统状态见 [STATUS](../STATUS.md)。

集成RAM系统提供中文Dockerman与RDA无线页面。
通过HTTP认证及隔离headless Chromium155.0.8059.41，
使用Playwright Core、1440×1000视口验证。
没有控制桌面浏览器；凭据、session、原始DOM/RPC和截图保持私有。

未认证请求返回403、`x-luci-login-required: yes`和中文登录表单，
属于正常LuCI认证。root/空密码POST后返回200和session cookie。
两个认证页面均为 `lang="zh-cn"`，
本次无页面JS错误或HTTP400以上响应。

| 检查边界 | 实际观察 |
|---|---|
| Dockerman概览 | 中文导航、汇总表和container/image/network/volume卡片；真实engine显示Docker29.6.1、API1.55、单CPU、744.43 MiB RAM |
| 服务状态 | 恢复后的RAM系统最初daemon未运行，UI正确显示socket连接失败；启动已验收RAM服务后显示真实engine |
| 无线概览/编辑 | 默认关闭radio；中文编辑器提供AP/STA、2.4 GHz、HT20/legacy、信道1–13、开放/WPA2-PSK、auto/CCMP |
| WPA2密码依赖 | 浏览器中选择WPA2后，AP和STA均显示密码输入；仅修改未保存表单，关闭弹窗未保存/应用 |
| 清理 | 停临时Docker并恢复UCI；wireless无待应用变化、radio仍关闭，SD/eMMC整盘RO标志均1，SSH正常退出 |

主要桌面页面和弹窗已视觉检查。
上游Dockerman高级环境表的长JSON会横向延伸，
没有声称手机/响应式布局通过，也没有点击Docker动作或启动无线。
复用此前真实容器和STA/AP证据；本次不写存储、不重启或安装。

| 私有证据 | SHA-256 |
|---|---|
| 浏览器结果 | `0d0f3ca263191263fa5fb97dfcfbaa58dfad5ab879572443775f331bc94b0d42` |
| Docker截图 | `cb83e6bf29f74dff99cabc161c95a84099f8e0e486d382a07d326aee9fff8ec6` |
| 无线编辑截图 | `bb80f4482b88e8da519c119549b6898f8cbf875cfbd67387aa22fa6f5c7930e7` |
| 无线安全截图 | `06dca040197efe6242f18c0489f87abf0ccb3f9a71f4b1981ae7d7f7d58dbefd` |
| RAM Docker启动/RPC | `1fa74297965460caaf64ca55e1fc1b9f645bf1b16daf157ff9ec303e3430527a` |
| 清理/只读状态 | `ce020b0f946a2c763716a1cea017316370818248b27d92e492a61ce072e4241e` |

本报告不涵盖p6/p9安装、磁盘根启动或跨重启持久化；
后续这些结果见[安装说明](../docs/installation-plan.md)及对应实机报告。
