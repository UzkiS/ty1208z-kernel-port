# 双代理核心与 unzip 干净 CI（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

[Application run 38415519493](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38415519493)
completed successfully on `3e89e05655edd749ae61683988e9ba44013fc24f`.
All four actual uploaded artifacts were downloaded and independently checked.
This is clean-build and isolated ARM QEMU evidence; the CI payloads are not the
locally built payloads used in physical board acceptance.

Each RAM variant's six manifest files passed byte-count and SHA-256 checks,
uImage header/data CRCs, ARM load/entry structure, exact zImage plus appended-DTB
equality, and expanded external-initrd size/placement checks. Runtime records
match their actual kernel, rootfs, config and package files. Test-input hashes
match tracked source at that exact commit and the delivered NTP/ZIP fixtures.
Actual console bytes and hashes match the records; each claimed marker appears
as a complete line in the downloaded console.

| Variant | uImage bytes / SHA-256 | Rootfs bytes / SHA-256 |
|---|---|---|
| plain applications | 3389876 / `7c4a193c7e727d05483a1ebab5ca55cd5618a61f96526189674933a78e54f21e` | 33291782 / `4ef13f9f31f1f41dd5691a4724f23143953ab69971d1032de1ace0ee363e916b` |
| measured-Ethernet router | 3437392 / `d39b0e34a9a1e359eba81f10c9722cbbd4a570a329cf7e6f9e11cbd09dfea043` | 33408217 / `a9ac88bb61d4a630c2e71da67bb08bc332ce02b5f2db6e7c91f1d63c21a3dd1d` |

Both variants pass 512-MiB and 240-MiB usable budgets with no disks or host
network. Actual Passwall-generated Xray and sing-box configurations pass SOCKS
and VLESS/TLS payload/certificate checks. Chinese LuCI, empty-root login, real
unzip extraction, time64/NTP era, DNS/HTTPS and nft counter markers pass. The
router additionally passes forwarding and Xray TCP/UDP TPROXY markers.

| Variant / usable MiB | Actual console SHA-256 |
|---|---|
| plain / 240 | `c3f27433c48a4cae88d8aa168141d1ff74e705b1e49701fa3ad6c4442d57b088` |
| plain / 512 | `5240b6faefc319a7924190b555bc28b57f4f45197c93472872a3722eb47a6793` |
| router / 240 | `e876cc9ada4be998f046fafc0c04a7e63880cbfb1e0f485e85540a6950716bde` |
| router / 512 | `9247d0b1d59fed4044d78492f232bd85eac5d06315c47b2eb4d688898f281984` |

Local checked result: `.work/ci-applications-38415519493-verified.json`.
Source/runtime scope is described in the [dual-core report](passwall-dual-core-20261013.md).
This does not establish sing-box TPROXY, physical plain-image boot, Docker
containers, Wi-Fi or persistent installation.
