# USB host0 register audit: offline acceptance

Date: 2026-10-12. This report records build, source, layout and emulation
checks. The candidate has not been booted on the TY1208Z. No USB device
transactions, controller initialization, firmware load or storage writes
were performed.

## Actual candidate

| Item | Observed result |
|---|---|
| Kernel | `6.12.112-ty1208z-usb-audit1` |
| uImage bytes | 2201344 |
| uImage SHA-256 | `391987d8831320d44bc96d4a4cc5e19660cafb6e8b0d18cca030b12e0519d8b2` |
| uImage CRC32 | `aca7f04e` |
| zImage SHA-256 | `4c7cb912ea547e20a4b421993f648f2f4fd1919755a8c22fb035940e04b89d32` |
| Expanded Image SHA-256 | `7503394e685b52bc4b6d9c3c7a0280977803a63534e61b196302e5e529cd14ce` |
| Decompression footprint | `0x00008000..0x005adde8`, below 16 MiB |
| Appended DTB SHA-256 | `55313ae68892a91597eed8add07b0a2c0305de7ea79c3be982b526132fb88180` |
| BusyBox SHA-256 | `4fc23ece22bca82e77ea17ac7c00f85d584dbf453055bffe147af81ab0b04ab2` |

The dedicated profile disables USB_SUPPORT, NET, BLOCK, MMC, MTD, modules,
SMP and debugfs. It observes only the host0 controls and fixed capability
words through an exact-resource platform driver. It has no USB host stack
or device driver. Details and pinned source ownership are in [USB](../docs/usb.md).

## Source and checks

The pinned SDK's MV100 `cpu-hi3798mv100.c` resolves the USB tuning revision
branch to SYSID0 `0xf8000ee0`. The audit therefore needs no SOC_FUSE read.
The clock readiness conditions are source-derived gates, not measured board
state. When they are not met, the audit skips EHCI/OHCI capability reads.

- The actual helper passed ASan/UBSan with exact read ordering and addresses,
  every required clock/reset/interface bit mutated, invalid SYSID0 values,
  and a write trap. It reads the five controls first and only then the four
  allowed capability words when ready.
- Compiled DT resources and kernel configuration passed the profile gate.
  Mutation tests reject resource changes, another board identity,
  unreviewed peripherals and broader subsystems.
- The base diagnostic was rebuilt; its generic ARM/time64, QEMU virt and RAM
  boot-protocol regressions passed after the shared patch extension.
- The USB candidate passed uImage/zImage CRC/structure, appended DT,
  static ARM ELF and actual decompression-footprint checks. The exact raw
  kernel and embedded initramfs passed generic QEMU virt shell and 2040
  clock/RAM-file timestamp checks; this does not emulate USB hardware.
- Latest repository lint and serial PTY tests passed, including USB report
  completion and rejection of missing audit output. A guarded RAM plan
  passed against the recorded loader inspection and matched the image hash
  and placement above. Live loader/DDR/bootcmd and device CRC must still pass
  before a physical boot.

Local build artifacts, raw logs and the RAM plan remain ignored. CI is
extended to reproduce this separate profile and upload it as UNTESTED;
the actual diagnostic run on `cf63f56` completed successfully:
[38269634107](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38269634107).
This is fresh build/emulation acceptance and does not replace a board boot.

## Remaining physical work

Measure inherited controls, SYSID0 and conditional capability words. Only
after that, implement and validate coordinated EHCI/OHCI clock/PHY ownership,
enumeration, exact RDA revision and licensed firmware, then bounded transfers,
scan, association and AP behavior. The existing optional RDA module build
does not establish any of these hardware results.
