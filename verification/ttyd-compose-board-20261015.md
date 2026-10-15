# ttyd 网页终端与 Compose 状态

日期：2026-10-15。基于已完成恢复默认的 `.3` 持久系统，使用串口与直接 HTTP/WebSocket 验证。

## 原因和修复

原系统 `ttyd --version` 返回 `1.7.7-unknown`，procd 服务运行，
默认配置绑定 `@lan` 并执行 `/bin/login`；缺少 `luci-app-ttyd`，因此 LuCI 无入口。
构建选择、feed 安装、系统 APK 必需清单及配置完整性检查现同时要求
`ttyd`、`luci-app-ttyd` 和 `luci-i18n-ttyd-zh-cn`。
同时显式选择原本由其他依赖选入的 `docker-compose`。

LuCI 来自固定 feed `8125d1288b359f6df505d3328b712bf059843fc8`，
身份由 [应用来源锁](../openwrt/applications/sources.lock.json) 记录。
只增量构建官方页面与翻译 APK，不修改上游页面或 ttyd 服务配置。

| APK | 大小（B） | SHA-256 |
|---|---:|---|
| `luci-app-ttyd-0.261012.35743.apk` | 3056 | `cde48b435df274f5229f96063b23a6a802b6b3278cfea24bf29edcd94d15c514` |
| `luci-i18n-ttyd-zh-cn-0.261012.35743.apk` | 2487 | `a2679c014fd6be522119a0a110f8dc29b0a6470ecb393787a4e8acf0daedad6f` |

## 实机结果

- 传输后重新校验两个 APK 的 SHA-256，通过 APK 正常安装并登记所有权；刷新 rpcd 菜单。
- 已登录 LuCI 的 `/admin/services/ttyd/ttyd` 和 `/admin/services/ttyd/config` 均返回 HTTP 200。
- 两个 JavaScript 资源可读，HTTP 7681 的 ttyd 页面返回 200。
- ttyd WebSocket 握手成功；经 `/bin/login` 输入 root，以系统当前空密码登录，执行
  `printf` 得到预定输出，然后退出。不是仅凭页面状态推断终端可用。
- 服务继续运行，没有新建 SSH 登录授权。

`docker compose version` 和 `docker-compose version` 均返回 v5.1.4。
实际 Dockerman 菜单只有概览、配置、容器、镜像、网络、卷和事件，未提供 Compose 项目页。
Docker Hub 当日 `louislam/dockge:1` 与 `portainer/portainer-ce:lts` 镜像索引
都列出 `linux/arm/v7`；仅核对平台清单，没有拉取、部署或宣称应用验收。

## 构建检查和交付范围

增量构建发现容器配置检查把已审核的 containerd 构建路径修正当作来源漂移。
现只规范化 `prepare_public_build_paths.py` 既有的单项 `GO_GCFLAGS` 修正后与上游锁比较，
仍记录实际构建配方哈希；额外追加未知内容的负例被拒绝。
真实组合配置检查、仓库 UTF-8/LF 与来源检查、修改 Python 的 Ruff 及构建脚本 ShellCheck 通过。

此次只增量安装网页插件，没有修改内核、执行整套镜像升级、重启或恢复默认。
未重跑未改变的容器运行和存储测试。已发布 `.3` 完整资产不变，
仍包含 ttyd 程序但不含其 LuCI 插件；当前盒子和后续源码构建已补齐。

随后已将同一插件打入 `.4` 的首刷、升级和配套 RAM 包并正式发布，`.3` 已撤下公开下载；
资产身份、包内检查和公开下载结果见[发布记录](release-20261015.4.md)。
