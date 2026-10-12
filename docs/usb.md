# TY1208Z USB host0 bring-up

The board's onboard RDA USB Wi-Fi `1e04:8888` is on bus 1, port 2 of the
Hinas EHCI host at `0xf9890000`. The running FDT, USB topology and original
boot log agree. This establishes wiring/controller identity, not operation
under the new kernel or an RDA firmware revision.

## Pinned source and measured resource boundary

SDK references are pinned to `07bug/HiSTBLinuxV100R005C00SPC060`
`a9f05973129d738e175416dd4a91b2c264ffcdd4`; file identities are recorded in
`reference/reference-manifest.json`. The selected `clk-hiusb2.c`, MV100 clock
binding and `cpu-hi3798mv100.c` carry Apache-2.0 notices. Preserve those notices
in future derived clock/PHY code; do not import a different chip's recipe.

| Resource | Runtime FDT / pinned source |
|---|---|
| EHCI host0 | `0xf9890000`, size `0x10000`, SPI 66 |
| OHCI companion | `0xf9880000`, size `0x10000`, SPI 67 |
| Shared CRG46 / CRG47 | `0xf8a220b8` / `0xf8a220bc` |
| PERI_CTRL_USB0 / USB1 | `0xf8a20120` / `0xf8a20124` |
| SYSID0 | `0xf8000ee0`; exact source mapping through `REG_BASE_SCTL + REG_SC_SYSID0` |

The SDK's host0 sequence asserts controller/UTMI/PHY reset, adjusts interface
mode, opens PHY reference clocks, writes PLL/test controls, releases PHY/port
reset and enables the shared controller clocks. It selects tuning by
`(get_chipid(0) & 0xf0) == 0x10`. Inspection of the pinned MV100 implementation
shows this low-byte branch comes directly from SYSID0; the SOC_FUSE high-part
read is unnecessary for that decision. The new audit reads SYSID0 only, not
the fuse block. Its actual value and USB control state remain unmeasured.

Host1 has different registers/resources and stays outside the first audit.
EHCI/OHCI host0 share PHY/clock ownership; later support must coordinate their
enable/disable lifetime and 32-bit DMA. The existing standalone RDA module is
not a host controller and cannot enumerate a device by itself.

## Independent read-only audit

`make usb-audit` builds `usb-audit1` after `make build`. The separate kernel
uses the measured CPU0/UART/timer and RAM footprint, with USB_SUPPORT, NET,
BLOCK, MMC, MTD, modules, SMP and debugfs disabled. Its sole added peripheral
is an exact-resource register observer, not an EHCI/OHCI driver.

The actual snapshot helper reads CRG46, CRG47, USB0, USB1 and SYSID0 in that
order. It reads only EHCI CAPBASE/HCSPARAMS/HCCPARAMS and OHCI revision when
the SDK-derived inherited clock/reset/interface readiness conditions hold.
Otherwise it reports that capability reads were skipped. It does not read
operational schedules, PORTSC, FIFOs or device endpoints, acknowledge IRQs,
write controls, initialize controllers or load any firmware. A reported
capability word is an observation; no expected value is invented for it.

Actual helper execution under ASan/UBSan checks control-bit mutations,
invalid revision values, exact read order/addresses and the absence of
writes. Compiled DT/config/image/placement and common RAM protocol checks
bound the resources and reject another peripheral or broader subsystem.
QEMU validates generic userspace/time64 only. The fixed board CLI profile is
`python tools/board_diag_cli.py --port COM9 --profile usb-audit1` after a
separately prepared RAM boot; its evidence requires the USB completion marker.
The built candidate and completed local checks are recorded in the
[offline acceptance report](../verification/usb-audit-offline-20261012.md).

## Remaining milestones

Measure inherited controls/revision/capabilities, then implement guarded host0
clock/PHY ownership and validate EHCI/OHCI enumeration with storage disabled.
Check exact RDA revision, firmware source/license/hash, bounded control and
bulk transfers, firmware startup, scan/association and AP support separately.
The Hinas log warned that the high-speed RDA bulk endpoints `03/83` advertise
64-byte maximum packets. Enumeration is insufficient to justify an override;
review the source's transfer sizing and actual hardware behavior first.
