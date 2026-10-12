# Native application matrix CI acceptance, 2026-10-13

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
UDP/NTP regression remains locally accepted and awaits its own remote CI.
