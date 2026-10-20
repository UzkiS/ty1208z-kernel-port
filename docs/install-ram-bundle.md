# TY1208Z CA 首次安装 RAM 配套包

仅适用于本仓库的 TY1208Z 高安版 / Hi3798MV100、1 GiB DDR 和固定 p6/p9 布局。
已安装 OpenWrt 的设备使用同一 Release 的 sysupgrade 包。
首次安装需要 TTL 串口与网线，先备份自己的设备；安装仅替换 p6/p9。

## 文件与校验

解压 `ty1208z-ca-install-ram-*.tar.gz`，先按 Release 的 `SHA256SUMS.txt`
校验整个下载包，再按包内 `RAM-SHA256SUMS.txt` 校验解压后的文件。
Linux 使用 `sha256sum -c`，Windows 可用 `Get-FileHash -Algorithm SHA256` 比较。

| 文件 | 用途 |
|---|---|
| `uImage-UNTESTED.bin` | 专用临时 RAM 内核；文件名来自构建器，不是 p6 刷写文件 |
| `rootfs.cpio.gz` | 与该 RAM 内核精确配套的 bootstrap |
| `userspace-system.RAM-ONLY.tar.gz` | RAM 系统补充用户空间及匹配模块 |
| `ty1208z-first-install-*.apk` | 临时系统中的首刷后端 |
| `first-install-manifest.json` 或 `first-install-manifests/` | 单版或三版首刷包与内核身份 |
| `manifest.json`、`checks/` | 构建身份、内存布局及来源记录 |

本包内核 ABI：`@KERNEL_ABI@`。first-install 全包复用已验收流程，最新包没有
重复整个 1 GiB 写入；生产内核已通过实机升级，DiskMan 已通过实机独立安装和功能验收。

## TTL / TFTP 启动

TTL 为 3.3 V、115200、8N1、无流控，只接 TX/RX/GND。启动时 Ctrl+C 停在
`fastboot#`。核对 `Hi3798Mv100 (CA)`、`DDR Size: 1GB`、Fastboot `3.3.0-dirty`，
以及本次启动输出的以下全部 allocation；地址或大小不同就停止，不用旧日志代替。

| 起点 | 字节数 |
|---|---:|
| `0x3fbfd000` | 4194304 |
| `0x3f8fc000` | 3145728 |
| `0x3f87b000` | 524288 |
| `0x3f878000` | 8192 |
| `0x3f843000` | 212992 |
| `0x3f742000` | 1048576 |
| `0x3f73e000` | 12288 |
| `0x3ef54000` | 8294400 |
| `0x3edbe000` | 1658880 |
| `0x3e5d4000` | 8294400 |
| `0x3e507000` | 835584 |

电脑启动 TFTP 服务，根目录为本包目录。电脑与板子选用同一 /24 内两个不同的
本地 IPv4 地址，板子地址必须空闲。以下 `HOST_IP`、`BOARD_IP` 均需替换为自己的
真实地址，不能原样输入。先记录原环境，只改临时变量，整个流程不用 `saveenv`。

```text
version
help tftp
help crc32
printenv bootcmd ipaddr serverip netmask autostart
getinfo ddrfree
setenv autostart no
setenv ipaddr BOARD_IP
setenv serverip HOST_IP
setenv netmask 255.255.255.0
tftp 1ffffc0 uImage-UNTESTED.bin
printenv filesize
crc32 1ffffc0 @UIMAGE_HEX_BYTES@
```

第一份传输必须为 **@UIMAGE_BYTES@ B**（`filesize=@UIMAGE_HEX_BYTES@`），CRC32
必须为 **`@UIMAGE_CRC32@`**。再传输 bootstrap：

```text
tftp 4000000 rootfs.cpio.gz
printenv filesize
crc32 4000000 @INITRD_HEX_BYTES@
```

第二份必须为 **@INITRD_BYTES@ B**（`filesize=@INITRD_HEX_BYTES@`），CRC32 必须为
**`@INITRD_CRC32@`**。任何长度/CRC 不同都停止。恢复刚才记录的 `ipaddr`、`serverip`、
`netmask`、`autostart` 临时值：原来存在的变量用 `setenv 名称 原值`，原来未定义的
用 `setenv 名称` 删除，再 `printenv` 核对。两份 CRC 已匹配后启动：

```text
bootm 1ffffc0
```

## 安装补充用户空间

RAM OpenWrt 通过 DHCP 获取地址。电脑同时将本包目录作为只读 HTTP 下载目录：
在该目录运行 `python -m http.server 8000 --bind HOST_IP`，将 `HOST_IP` 换成电脑地址。
临时系统串口中运行以下命令，`HOST_IP` 同样需替换：

```sh
ip -4 address show eth0
wget -O /tmp/userspace-system.RAM-ONLY.tar.gz http://HOST_IP:8000/userspace-system.RAM-ONLY.tar.gz
echo '@SUPPLEMENT_SHA256@  /tmp/userspace-system.RAM-ONLY.tar.gz' | sha256sum -c -
```

补充包 SHA-256 必须与包内清单一致，随后解压到当前 RAM 根，安装首刷 APK：

```sh
tar -xzf /tmp/userspace-system.RAM-ONLY.tar.gz -C /
rm /tmp/userspace-system.RAM-ONLY.tar.gz
sh /etc/uci-defaults/98-ty1208z-docker-network
rm /etc/uci-defaults/98-ty1208z-docker-network
wget -O /tmp/first-install.apk http://HOST_IP:8000/@INSTALLER_FILE@
echo '@INSTALLER_SHA256@  /tmp/first-install.apk' | sha256sum -c -
apk add --allow-untrusted --no-network --repositories-file /dev/null /tmp/first-install.apk
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart
```

APK 的 SHA-256 同样必须匹配清单。本板只有一个物理网口，默认是 DHCP 上联。
串口中将管理规则限定到自己的电脑地址；以下 `HOST_IP` 必须替换：

```sh
uci set firewall.ty1208z_install_management=rule
uci set firewall.ty1208z_install_management.name='Temporary installation management'
uci set firewall.ty1208z_install_management.src='*'
uci set firewall.ty1208z_install_management.src_ip='HOST_IP'
uci set firewall.ty1208z_install_management.proto=tcp
uci set firewall.ty1208z_install_management.dest_port='80 443'
uci set firewall.ty1208z_install_management.target=ACCEPT
uci set firewall.ty1208z_install_management.family=ipv4
uci commit firewall
/etc/init.d/firewall reload
```

打开 `http://板子实际DHCP地址/cgi-bin/luci/`，默认账号 root、空密码。
“系统 → 备份与更新”上传同一 Release 的 first-install 包。
三版下载集合选择 `ty1208z-ca-bridge-first-install-*`、`ty1208z-ca-hybrid-first-install-*`
或 `ty1208z-ca-nat-first-install-*`；旧单版文件名为 `ty1208z-ca-first-install-*`。
首次安装要启用所选类型的默认网络时，取消“保留配置”；保留时会沿用临时系统网络，
临时管理规则也会被保留。纯 NAT 版持久启动后默认从 Wi-Fi 的 `192.168.50.1` 管理。
校验通过后安装，等待完整写入、读回和自动重启，不断电。

首次持久启动会自动扩容 p9 到完整 6846 MiB。之后只使用 sysupgrade 包。
磁盘管理在“系统 → 磁盘管理”，持久自动挂载在“系统 → 挂载点”。
默认不自动格式化或挂载 SD/USB，用户按需要配置；系统 eMMC 的格式化由后端拒绝。

更多说明：<https://github.com/UzkiS/ty1208z-kernel-port/blob/main/docs/installation-plan.md>。
来源与许可：<https://github.com/UzkiS/ty1208z-kernel-port/blob/main/LICENSES/README.md>。
