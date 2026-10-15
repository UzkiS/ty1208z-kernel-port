# 恢复默认页面按钮与路由修复

日期：2026-10-15。修复范围为已安装系统的恢复默认 LuCI 页面，不改变 ext4 重置事务后端。

## 原因与修复

预检成功且具有写权限时，原页面向 LuCI `E()` 传入 `disabled: false`。
固定版本 LuCI 的 DOM 属性处理仍将其写为 `disabled="false"`；HTML 布尔属性只看是否存在，
浏览器因此始终禁用按钮。此前只模拟属性对象的测试没有覆盖浏览器的这一语义。

成功分支改传 `null`，让真实 LuCI 省略该属性；预检失败或只读时继续禁用按钮。
菜单与视图改为 `admin/system/reset` 和 `system/reset`，旧 `admin/system/ty1208z-reset`
通过 LuCI alias 兼容。后端命令、ACL 和 APK 名不变。

## 回归与实机结果

- `tools/test_native_reset_ui.cjs` 使用固定 LuCI feed 的实际 `luci.js` 与 jsdom 26.1.0，
  检查真实 DOM 的属性存在性和 `button.disabled`，验证可点击、先确认后请求、RPC 错误通知、
  只读/预检失败禁用以及新旧路由。此测试模拟 RPC，不会重置设备。
- 同一测试对 `.4` 的旧页面源码报错，定位到成功分支仍含 `disabled` 属性。
- 实机通过正常 APK 升级安装与 `.5` 升级包相同的重置包；传输 SHA-256 校验通过。
  APK 为 `ty1208z-reset-1.0~47569d200152-r1.apk`，436607 B，SHA-256
  `8017347f78ed1b56d6368d9e94ce826c800c2bd8d4ea62935f9ed9abe76ba0ff`。
- 登录后的新旧页面均 HTTP 200，LuCI 解析到 `system/reset`，依赖满足且具有写权限。
  HTTP 返回的 JavaScript 与源码逐字节相同；真实 RPC 预检退出 0 并返回 `TY1208Z_RESET_READY`。
- 升级暂存根、首刷暂存根和实际首刷 ext4 镜像内的新视图与菜单均与源码逐字节一致，
  新根不含旧路径的重复视图。

本次没有执行新的实机恢复默认、整套 sysupgrade、完整首刷或重启；
已有后端实际重置与数据保留证据见[恢复默认实机记录](factory-reset-board-20261015.md)。
CLI DOM 测试不等于浏览器自动化或新的硬件重置验收。

`.3` 和 `.4` 包含该按钮问题，修复随 `.5` 发布；旧版文件身份保留供追溯。
