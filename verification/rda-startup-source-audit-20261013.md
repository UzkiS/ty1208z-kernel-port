# RDA 初始化补充源码审计（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

Three additional public driver directories were inspected for an implemented
named-iovar transport. Nine source/header files were fetched at exact commits;
their URLs, sizes and SHA-256 are in the
[audit manifest](../reference/wifi-rda-startup-audit.json). No firmware or
complete kernel tree was fetched for this audit, and none of these alternatives
was executed, compiled or substituted into the current port.

| Repository | Fixed commit | Driver directory |
|---|---|---|
| `zx297520v3-mainline/linux-3.4` | `80e1fec813691ceb16567581c3fe4d49e4bab7f3` | `drivers/net/wireless/rdaw5995/rdawlan` |
| `zx297520v3-mainline/linux-3.4` | same | `drivers/net/wireless/rdaw80211/rdawlan` |
| `Deema35/i96_kernel` | `2f133257b856aee3364454045ec74ee8dd998df1` | `drivers/rda/net/rdawlan` |

All three `wland_cmds.c` files initialize the named set/get return value to
zero, place the transport body under `#if 0`, and return zero. The get function
therefore leaves the caller's output unchanged while reporting success.
Their cfg80211 startup source still calls the named roaming helper and band
update; band queries include `get_phylist`, `nmode` and `mimo_bw_cap`. These
files provide no functioning replacement for the current port's reproduced
[initialization blocker](wifi-startup-20261013.md).

In the `rdaw5995` alternative, band update reads local `phy_list` after the
disabled getter and later overwrites bandwidth/nmode/band defaults. Neither
an untouched output nor those source defaults measures this board's radio
capabilities. Returning success or copying those defaults would conceal the
missing operation rather than establish RDA support.

The pinned USB port's first firmware-state query is `WID_MEMORY_ADDRESS`
(`0x201e`); firmware download/run and preinitialization precede its
`WID_CHIP_VERSION` (`0x0416`) and firmware-version (`0x3001`) queries. The
revision byte does not identify the chip family, and source-selected
`WLAND_VER_91_H` plus USB `bcdDevice=0000` is not a physical measurement.
No pre-download chip-identification transaction was performed in this audit.

Modern-kernel [USB/RDA enumeration](usb-host-board-20261013.md) now passes,
but the running Chinese router image excludes USB/Wi-Fi. The next radio work
requires actual chip-family/revision evidence, matching firmware provenance,
and a supported initialization/capability path. No firmware selection,
download, manufacturing command, guessed WID mapping or radio claim was made.
