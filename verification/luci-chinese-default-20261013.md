# Simplified Chinese application/router default

The user requested Chinese as the default in future builds. The shared
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

| New offline payload | Bytes | SHA-256 | CRC32 |
|---|---:|---|---|
| uImage | 3436544 | `80bcfbf09f329ad96ed7fd2de44fb946f8822b99b7af53979cc9de8054e1c3c4` | `9d11beca` |
| External initrd | 21142267 | `5d355a83991dc858643244bb635e517444f0d42e40f8836eea0e2eb384b258f7` | `3ff40518` |

Raw kernel SHA-256 remains
`329b834337b842113001984da7d13b16f601aed49694da89e5bdc79aeeeafab2`.
The wrapper DTB changes only with the new initrd length. All six packaged
payload identities, actual console/provenance and fixture-source hashes were
independently verified. The three catalogue sizes are base 146072, firewall
18960 and Passwall 35756 bytes. The new candidate is saved separately from
the booted TX image.

Core lint/build/time64 tests pass; the language script also passes shellcheck.
This Chinese candidate has offline acceptance only. The currently running
physical router retains the previous image/configuration; no reboot, flash
or persistent boot change was issued for this language preference. Fresh
application CI remains separate from local QEMU acceptance.
