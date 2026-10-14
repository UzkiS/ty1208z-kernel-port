# RDA 接口启动失败回退（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The actual optional cfg80211 startup callback now clears `VIF_STATUS_READY`
when initialization fails, while holding the existing synchronization mutex.
It previously left the flag set before attempting roaming, interface setup or
band configuration. Dependent callbacks could therefore treat failed startup
as ready. Other state bits are preserved; a subsequent successful initialization
or the existing already-up path still enables the interface.

`tools/test_wifi_startup.py` extracts the real startup callback, legacy roaming
helper and named-iovar setter from the patched source. ASan/UBSan checks every
startup stage against four negative errors, both initial READY states, retries,
the already-up path and balanced locking. Later-stage failures/successes use
controlled helper replies; they verify rollback and sequencing, not a real
firmware operation. Marker: `RDA_STARTUP_ROLLBACK_PASS`.

The test also executes the real legacy roaming helper with the real unsupported
named-iovar transport. Both values of `roam_on` produce `-EOPNOTSUPP`, stop
before interface/band setup and leave READY clear. This is a reproduced
functional blocker, not a passing association or radio test.

## Confirmed initialization blocker

The actual ARM module was preprocessed using its Linux 6.12 kernel configuration
and USB compilation flags. The active path is:

`wland_usb_probe` -> `wland_bus_start` -> netdev registration ->
`wland_netdev_open` -> `wland_start_chip` -> `wland_cfg80211_up`.

`cfg80211_up` first calls `wland_dongle_roam`, which attempts `roam_off` and
other named-iovar settings. These requests have no implemented RDA transport.
Even after solving that stage, `wland_update_wiphybands` attempts `get_phylist`,
`nmode` and `mimo_bw_cap` through the same missing path. These are active code
in the USB module, not merely disabled SDIO or test-mode branches.

The pinned RDA source has typed WID commands and uses actual link-loss and
short-GI WIDs in preinitialization, but that does not establish equivalence to
the named roaming/PHY queries. No guessed names-to-WID mapping, synthetic
capability reply or silent success was added. USB-controller acceptance,
chip/firmware identification and completion of the real RDA initialization
path remain required before Wi-Fi can be used.

The existing USB probe also selects `WLAND_VER_91_H` in source; this is not a
measured chip revision. Firmware/revision and association/AP/performance remain
unverified on TY1208Z. Earlier key/operation tests remain valid within their
reported scope and do not overcome this startup blocker.

## Local build identity

| Item | Result |
|---|---|
| Kernel release | `6.12.112-ty1208z-wifi-port` |
| Module bytes | 339248 |
| Module SHA-256 | `2e6b1a4a43e3d86da4681466967f1e0ab11fc1073f1a3815b111f9bb10688eb9` |
| Port patch bytes | 80760 |
| Port patch SHA-256 | `7a6ac2474cbb2a3584626ac07ef139ccd19e8ada953a0147e2244142cd3b1e35` |
| Config SHA-256 | `0f2d638059c01eb4f91a0ed647ad81114f3cff109ae8359ab72474ee881ede08` |

All existing WID/control/key/operation sanitizers and full ARM module
link/modpost/identity checks passed. This supersedes the earlier local module
identity, remains compile-only and must match its exact kernel/config.

The full remote diagnostic [run 38304430531](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38304430531)
also passed on `fbc1e79`, including the actual startup rollback regression
and fresh module link. It does not resolve the reproduced initialization
blocker or provide hardware USB/radio evidence.

The downloaded remote module's manifest files and the actual standalone
`RDA_STARTUP_ROLLBACK_PASS` marker were subsequently verified. Remote module
bytes/SHA are 339376 /
`cdd503f7d2209f8020a8a12fe6aa9ade1560aa3e58763d94ec176cd5501583e9`,
and the build-log SHA is
`8544895e4f8fb305a5f0ffdf213c24d9eb5637f340722df75764155d902b3ad5`.
Its generated patch matches the recorded startup version. The remote config
differs in Rust compiler availability metadata, although Rust is not enabled;
remote/local module identities are kept separate. The later local
[scan changes](wifi-scan-20261013.md) supersede the local identity above.
