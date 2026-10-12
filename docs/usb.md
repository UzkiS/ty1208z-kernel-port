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

Measure inherited controls/revision/capabilities, then prepare a distinct
guarded RAM host0 profile and validate EHCI/OHCI enumeration with storage disabled.
Check exact RDA revision, firmware source/license/hash, bounded control and
bulk transfers, firmware startup, scan/association and AP support separately.
The Hinas log warned that the high-speed RDA bulk endpoints `03/83` advertise
64-byte maximum packets. Enumeration is insufficient to justify an override;
review the source's transfer sizing and actual hardware behavior first.

## Optional compile experiment

`make usb-host-compile` separately compiles `clk-ty1208z-usb.o` and the
mainline EHCI/OHCI core/platform objects. It produces no DTB, kernel image or
RAM-boot permission. The option is absent from all existing diagnostic,
native-network and router images. Its distinct board compatible has no DTS
in this repository; current images cannot bind this provider.

The new GPL-2.0-only implementation represents the pinned SDK's hardware
register protocol as independent command tables and bounded read/modify/write
operations. The test verifies the original file's locked hash, preserves its
full Hisilicon/Apache-2.0 notice and executes its actual host0 functions in a
temporary oracle; no SDK C implementation is vendored into the driver. For
all 256 low-byte revisions and eight initial control states, the new helper
must match every original write and delay through last-user shutdown. Actual
helper/oracle code runs under ASan/UBSan. Invalid SYSID0 causes no writes;
stuck reset/interface or missing required clock bits cause failure and the
documented shutdown sequence before an HCD can start. This cannot establish
PLL stability or the board's actual revision/capabilities.
Shutdown readback failures are reported as errors rather than as a successful
clock/PHY stop. The [compile report](../verification/usb-host-compile-20261013.md)
records the actual objects and completed local checks.

One common-clock-framework core exposes one provider output to both HCDs.
Its sleepable prepare/unprepare callbacks use CCF ownership and serialization,
rather than separate EHCI/OHCI reset sequences. Mainline platform HCDs take
and release clocks around probe/removal; their default coherent DMA mask is
32 bits. The clock provider performs no control writes during registration
and has no shutdown callback that could reset a still-running companion.
Last-user shutdown follows the SDK; it does **not** restore the inherited
analog PHY tuning. PM, modules, network and storage are disabled for this
compile experiment. Companion lifetime, probe-failure and system-shutdown
behavior still require validation in the eventual real host profile.
