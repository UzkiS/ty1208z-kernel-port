# 简体中文与空密码默认配置（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Simplified Chinese is the image default. The shared
application configuration now selects `LUCI_LANG_zh_Hans` and the LuCI base,
firewall and Passwall `zh-cn` packages. Feed installation explicitly includes
the base/firewall translations. A reviewed first-boot UCI script sets
`luci.main.lang=zh_cn`; users can change it afterward.

The actual built-rootfs gate checks the script bytes, all three nonempty LMO
catalogues and installed package manifest. Isolated ARM QEMU checks the
first-boot UCI value, actual HTML `lang="zh-cn"`, and translated username and
password labels. Both 512-MiB and 240-MiB usable trials record
`LUCI_CHINESE_DEFAULT_PASS` together with the existing NTP/time64, DNS/TLS,
authenticated UI, SOCKS and TCP/UDP TPROXY results.

| Usable MiB | Actual console bytes | SHA-256 |
|---:|---:|---|
| 512 | 126943 | `32d709018033e041599f50c92914949231bf3bc59289c5436c46fb10344b658d` |
| 240 | 126908 | `a1975fc5b96a0eed63d31f91f78af2af9a5f364bbc7a7321eee277c2ef1a22fa` |

The new language marker is optional for previously measured RAM artifacts.
If recorded, its actual console evidence is required. Actual-artifact
regression verifies backward acceptance and rejects a missing console marker
even when the console hash is updated. Resource/payload/provenance mutations
and the two device-CRC boot gates also pass.

| Chinese RAM payload | Bytes | SHA-256 | Device CRC32 |
|---|---:|---|---|
| uImage | 3436544 | `80bcfbf09f329ad96ed7fd2de44fb946f8822b99b7af53979cc9de8054e1c3c4` | `9d11beca` |
| External initrd | 21142267 | `5d355a83991dc858643244bb635e517444f0d42e40f8836eea0e2eb384b258f7` | `3ff40518` |

Raw kernel SHA-256 remains
`329b834337b842113001984da7d13b16f601aed49694da89e5bdc79aeeeafab2`.
The wrapper DTB changes only with the new initrd length. All six packaged
payload identities, actual console/provenance and fixture-source hashes were
independently verified. The three catalogue sizes are base 146072, firewall
18960 and Passwall 35756 bytes. The Chinese candidate is saved separately from
the earlier TX image and is now the running physical RAM image.

Core lint/build/time64 tests pass; the language script also passes shellcheck.
Fresh application CI remains separate from local QEMU acceptance.

## Physical Chinese acceptance

After the user restored the serial 3.3-V supply and stopped the original CA
loader, fresh inspection, bounded RAM placement, both TFTP receipts/sizes
and both device CRCs passed. Original loader network values were restored
before boot. No flash or persistent boot change was performed.

The untouched first boot reported `luci.main.lang=zh_cn`, all three catalogue
sizes above and the delivered peer-DNS default. Native release/router DT and
Ethernet identity were checked before restoring the latest 15 saved user
configuration/authentication files; every restored file hash passed. The
saved LuCI preference was then set to `zh_cn` in this RAM system. Password
and authentication material stay in ignored local evidence.

Actual host HTTP validation observed unauthenticated Passwall access returning
403 with the login-required header, HTML `lang="zh-cn"`, and translated
username/password labels. Existing credentials then produced HTTP 200 and
the authenticated Passwall page, also with Chinese HTML language. Recorded
login/authenticated page sizes are 17818/128880 bytes, with SHA-256:

- Login: `ab86f5568b2913980b69b91847a1bc8b74ebb0b1ad54e3ffff5469e8c19148ff`.
- Authenticated: `36a0ca38f5e92f3487c9a34b71d79d3414d92cdafcb6fdcef2e143fce288c1d7`.

The normal current 2026 clock and RAM-file time64 probe passed. The physical
ARM namespace HTTPS/SOCKS/forwarding/TCP/UDP TPROXY fixture and bidirectional
Ethernet TCP also passed with configuration restored and temporary rules
removed. Exact evidence identities and test limits are in the
[physical router report](openwrt-router-board-20261013.md). These results do
not establish external Ethernet routing, Wi-Fi/AP or persistent installation.
