# USB host0 clock/PHY compile experiment

Date: 2026-10-13. **Offline compile acceptance only. No host0 board startup,
device enumeration, RDA firmware loading or Wi-Fi operation was performed.**

The separate `make usb-host-compile` target compiles the optional provider and
the existing Linux 6.12.112 EHCI/OHCI core/platform objects. It does not produce
a DTB/uImage or grant RAM-boot permission. Existing Ethernet/router candidates
remain separate. The distinct USB experiment compatible has no board DTS.

## Inputs and scope

- SDK: `07bug/HiSTBLinuxV100R005C00SPC060`, commit
  `a9f05973129d738e175416dd4a91b2c264ffcdd4`;
  locked `drivers/hisilicon/clk/hi3798mx/clk-hiusb2.c`.
- Linux: pinned 6.12.112 with the regenerated project patch.
- Host compiler: Ubuntu GCC 13.3.0 `arm-linux-gnueabihf`.
- Added provider resources: exactly CRG46/CRG47, USB0/USB1 and SYSID0, each
  four bytes. No host1 or fuse mapping.
- Config: built-in generic EHCI/OHCI; BLOCK, MMC, MTD, NET, PM, modules,
  SMP, debugfs and USB storage disabled.

The new GPL-2.0-only helper independently implements register-protocol facts
from the pinned SDK. The source-derived test oracle retains the original full
Hisilicon/Apache-2.0 notice in its temporary translation unit; no SDK C bodies
are vendored into the driver. SYSID0 supplies the documented low-byte tuning
decision. Its actual board value and controller capabilities remain unknown.

## Completed local validation

`tools/test_usb_host0.py` verifies the original SDK file hash and executes its
actual host0 enable/disable/tuning functions alongside the actual new helper
under ASan/UBSan. All 256 low-byte revisions across eight initial control states
produce the same 2048 write/delay/shutdown traces. Every access is restricted
to the five mapped controls; writes to SYSID0 or another address fail the test.
Zero/all-ones SYSID0 causes no writes. Injected reset/interface bits that cannot
clear and required clocks/interface bits that cannot set cause failure and
shutdown. Shutdown readback failures are also rejected.

The actual new clock provider plus upstream EHCI/OHCI core/platform objects
compile successfully as ARM ELF32 EABI objects. The builder compares its
provider/helper source against the authoritative overlay before compilation.
The final provider object is 5896 bytes, SHA-256:

`88661811ba911dfce606fc28d33e11c3a08a3dc2442d32ae99f096620c92e296`

Object identities and resolved config are retained locally in
`artifacts/usb-host-compile/checks.json` and `linux.config`; they are not boot
artifacts. Repository lint, serial PTY regression, ordinary diagnostic build,
image/layout checks, QEMU time64 and ordinary RAM-boot CRC/DDR gates also pass.

## Remaining acceptance

The provider uses one shared CCF core so companion consumers share first-prepare
and last-unprepare ownership. Generic HCDs retain their normal 32-bit DMA and
probe/removal/shutdown handling. These framework paths were source-reviewed;
their actual dual-HCD lifetime and failure/shutdown behavior on this board is
not established by the MMIO trace test or object compilation.

First measure controls/SYSID0/capabilities with the independent read-only USB
audit. Then prepare and validate a narrow host0 RAM profile, actual device
enumeration, RDA revision and firmware identity, scan/STA/AP and reconnect.
SDK last-user shutdown does not restore inherited analog PHY tuning. No
hardware-verified USB or Wi-Fi claim follows from this experiment. A CI step
has been added; this report does not claim that the new step has completed.
