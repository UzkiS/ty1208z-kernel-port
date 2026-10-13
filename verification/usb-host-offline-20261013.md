# USB host0 enumeration image: offline acceptance

Update: the later [physical clock/capability experiment](usb-clock-audit-board-20261013.md)
passed and its measurements were reviewed. The exact enumeration profile now
passes the bounded RAM planner; the earlier denial below describes its original
offline milestone. Enumeration itself remains separate physical acceptance.

Date: 2026-10-13. **Built and emulated, not booted on TY1208Z.** The guarded RAM
boot planner deliberately rejects the image pending the independent physical
USB register/capability audit. There is no USB/RDA/Wi-Fi hardware acceptance.

## Actual artifact

Separate `make usb-host` output: `artifacts/usb-host1`.

| Field | Local build |
|---|---|
| Kernel release | `6.12.112-ty1208z-usb-host1` |
| uImage size | 2247932 bytes |
| uImage SHA-256 | `8f32dd5961f231819c6c430c5a8869f4566c3ed207bea0f87b6884d8cd52e299` |
| uImage CRC32 | `cad54a66` |
| Raw zImage SHA-256 | `2c12812d7770ea0201fb03a4575c3d86e1e873c3789604c2336eceee880fa143` |
| Kernel physical range / BSS end | `0x00008000 .. 0x00576de8` / `0x005aa750` |
| Board memory bound | low 256 MiB, low 16 MiB allocation reservation |

The dedicated DTS has only measured UART/timer/GIC, one USB host0 shared clock
provider, EHCI `0xf9890000`/SPI 66 and OHCI `0xf9880000`/SPI 67. Both HCDs
reference the exact same provider output. Host1, block/MMC/MTD, network,
class drivers, INPUT/VT/HID, PM, modules, SMP and debugfs are excluded. No
RDA module or firmware is present. The provider/helper continue to match the
pinned-source differential checks described in the [compile report](usb-host-compile-20261013.md).

## Completed checks

- Ordinary diagnostic `make build`/`make test`, repository lint and serial PTY
  regression passed after the shared tooling/init changes.
- The standalone host0 kernel links, CRC/image/DT/ARM ELF checks pass and its
  actual decompressed Image/BSS footprint remains below the 16-MiB boundary.
- Actual compiled DT/config profile checks pass. Mutating each host control,
  MMIO range, IRQ, compatible, shared clock/phandle or adding a property fails.
  Storage/class drivers, other board profiles, missing HCDs, larger RAM and an
  extra host are rejected.
- The actual host artifact is rejected by the normal RAM planner with
  `USB host0 image is offline-only pending physical USB register/capability audit`.
- QEMU boots the same raw kernel/initramfs with virt's DT, no host network or
  disks. ARM `usb-diag` reports both platform bindings unbound and zero EHCI,
  OHCI and RDA devices. This verifies the observer's real shell execution,
  not MV100 HCD operation. Future-clock/file timestamps and BusyBox stat pass
  at 2040 in that isolated guest.

Local QEMU, resolved config, manifest and layout logs remain under
`artifacts/usb-host1/checks`. Clean diagnostic CI passed on `3355c5b` in
[run 38291376864](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38291376864),
including the shared clock/PHY differential compile experiment, standalone
host image, actual profile/config checks, QEMU observer/time64 and deliberate
RAM-boot denial. The result supplies offline reproduction, not USB hardware
acceptance.

## Required physical evidence

Measure SYSID0 and inherited USB controls/capabilities first; none are inferred
from the emulation. Then review the exact branch and controller layout, open
the dedicated RAM gate, and test cold-start enumeration, EHCI/OHCI shared
lifetime/failure/shutdown, RDA revision, firmware identity, scan/STA/AP and
reconnect. Preserve existing Hinas and the working CA loader throughout.
