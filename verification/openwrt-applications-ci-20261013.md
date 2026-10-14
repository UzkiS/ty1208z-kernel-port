# 原生应用矩阵 CI 验收（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

[Run 38287461985](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38287461985)
completed successfully on `62db42b22c90e7293986e8076745b9119e80939e`.
Both matrix jobs built a fresh pinned native compiler/musl, built applications,
ran ARM QEMU acceptance and uploaded separate external-initrd RAM candidates.
The plain job completed at 19:51:07 UTC and the Ethernet/application job at
19:57:44 UTC on 2026-10-12.

This run predates the later UDP and NTP fixtures. It establishes native
application/TCP integration and RAM packaging acceptance, not those later tests
or any physical TY1208Z result.

## Inspected remote evidence

All four uploaded artifacts were downloaded to ignored local work storage.
The packaged file lengths/SHA-256, legacy image header/data CRCs, exact
zImage-plus-DTB payload, load/entry and gzip expansion lengths were verified.
External initrds are at `0x04000000`; neither upload defines an install recipe.
The QEMU records' kernel/rootfs/config/package hashes match those packaged
files. Console lengths/hashes and every recorded standalone success marker
were checked, including the actual time64 timestamp at 2040.

| Variant | QEMU budget | Console SHA-256 |
|---|---|---|
| Plain applications | 512 MiB | `1ecde6da0350562c4104e7a81523de96d2f3cd7fc2777c12fe78b3a83459dcfe` |
| Plain applications | 256 MiB, `mem=240M` | `7a9ef053965fdfed36907e6ba06c8f46385cde221d7ecf0c5c2300a34db28e76` |
| Ethernet/applications | 512 MiB | `962fa968311e4185733931766752497c252bc4c4ea260602b3de39d7fdcd654c` |
| Ethernet/applications | 256 MiB, `mem=240M` | `f6266bdbd58b6bfc6f51212343fd49fa1522c5cb91d399cec91406981aaee6d8` |

All four cases contain certificate/DNS/HTTPS time64, authenticated Passwall
LuCI, rpcd, actual Xray SOCKS and TLS, nft expressions/counters and the final
`OPENWRT_APPLICATIONS_QEMU_PASS` marker. Both integrated cases also contain
`OPENWRT_ROUTER_FORWARDING_TIME64_PASS` and `PASSWALL_TPROXY_TCP_TIME64_PASS`.
No UDP or NTP success marker is present in these older records.

## Remote RAM artifact identities

| File | Bytes | SHA-256 |
|---|---:|---|
| Plain uImage | 3391804 | `612b99ff46d5337cbecc5a265aff865a983f896ae8e351d9756cd7893276a407` |
| Plain external rootfs | 20923158 | `ba48f87dfed60d90b6756c1634e0c936e4d9b403c4726542373c9a5f19defe6f` |
| Integrated uImage | 3436584 | `cc3e2d45da76de4f529d493e81891a3bbff3c4596cf681524bc74c822d260f97` |
| Integrated external rootfs | 21043349 | `02c9718c3f79af3121cdd1df98cdae8a135089b998a2ac7b04fafca8a788918c` |

Whole-file CRCs are `cdc469da`/`84373152` for the plain kernel/initrd and
`53b6b1ae`/`8a7d3b7c` for integrated kernel/initrd. These are the remote
`62db42b` outputs, distinct from later locally recorded candidates. They have
not replaced the local physical-test artifacts and have not been transferred
to the board.

The guests used QEMU virt/Cortex-A7/single-core, no host-network access and no
disks. This does not verify MV100 peripherals, CA RAM boot, sustained physical
traffic, physical routing/TPROXY, NTP service, Wi-Fi or installation. Later
UDP/NTP remote acceptance is recorded separately below.

## UDP and NTP matrix accepted remotely

The later [run 38298432025](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38298432025)
completed successfully on `c25f83d788169610045eef96788cc23f95f04fba`.
Both matrix jobs and every step were inspected. The plain job ran from
19:57:47 to 21:41:42 UTC and the integrated job from 19:57:47 to 21:52:57 UTC
on 2026-10-12. Fresh pinned native toolchains, full applications, 512/240-MiB
QEMU trials and separate external-initrd packaging all succeeded.

All four uploaded artifacts were downloaded. Each RAM manifest's actual
file lengths/hashes, uImage header/data CRC, appended DTB, initrd gzip length
and load addresses were checked. QEMU kernel/rootfs/config/package identities
match the packaged files. Every console's byte length/hash and exact required
marker set were verified. Test-source hashes also match the files in the
actual `c25f83d` commit; fixture source/binary provenance remains separate
from the delivered rootfs.

All four consoles contain the four distinct installed-NTP-client cases with
the expected seed/target pairs. Actual corrected times were at most three
seconds after the target; every server reported positive replies and zero
rejected requests. Both integrated trials contain actual UDP TPROXY packet
counters and the TCP/UDP success markers. The executed router fixture requires
forward and reverse UDP delivery, and direct traffic failure before/after
Passwall, not merely construction of firewall rules. Emulated transfers
establish delivery, not board throughput.

| Variant | Usable memory | Console SHA-256 |
|---|---|---|
| Plain applications | 512 MiB | `1c743a9ab6cd5fde135eace236a2ba4243e17cbffd2017b2f3e0b05acb337c17` |
| Plain applications | 240 MiB | `79d24d90fab62f360877dd3a9e5cfa696d433054532ef1161c4c15e9ec464a39` |
| Ethernet/applications | 512 MiB | `72decfa23e7842adbe758e4614b95e3bf6894b9e77d5cc004b8741f0204dbcfb` |
| Ethernet/applications | 240 MiB | `e8edfcf0b3abf4d144c5506fd24d4756e4bada58b167852b476354d886f6fa0c` |

| Remote `c25f83d` RAM file | Bytes | SHA-256 |
|---|---:|---|
| Plain uImage | 3391804 | `61fcbdb8e2407f82da06ff83f6b0c7a42ac85bb8fd0134707a2a19b79cc67c58` |
| Plain external rootfs | 20923232 | `0ead3f0df5235c35d218512de1da07e3a73f670836861c9c01f617c2c8cc7191` |
| Integrated uImage | 3436584 | `ca79ad16f31a4288e6b52fc241775a8d731261ed1c29b171767d7699120d5dcc` |
| Integrated external rootfs | 21043524 | `87661537e019392aed403f7a1690d7befd0697d939a8fd1db5112f9673f20769` |

The static remote NTP fixture binary is 42096 bytes, SHA-256
`ed944c93286928df9588e41eaf1a02f3cc941afd87fcb41fc42e7aec02485e15`.
These remote artifacts have not replaced the local physical-test candidates.
No physical peripherals, NTP service, routing/proxy performance, Wi-Fi,
persistent storage or complete system Y2038 acceptance is implied.
