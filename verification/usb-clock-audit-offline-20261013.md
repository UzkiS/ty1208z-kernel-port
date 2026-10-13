# Guarded USB host0 clock/capability experiment

Date: 2026-10-13. Offline build and emulation acceptance only. This candidate
has not yet run on the TY1208Z. USB enumeration, RDA firmware, Wi-Fi STA/AP
and ordinary `usb-host1` RAM-boot permission remain pending.

## Exact candidate

| Item | Built result |
|---|---|
| Kernel | `6.12.112-ty1208z-usb-clock-audit1` |
| uImage bytes | 2200676 |
| uImage SHA-256 | `365f8711150fd474d5d73ce929975b175427ba36a2d4e6c96108f539889abecf` |
| Whole-file CRC32 | `25765904` |
| Raw zImage SHA-256 | `fb8d7225be2842ba4c993937f5b7ccfc500100fa373ea70321934072de1a0ae7` |
| Appended DTB SHA-256 | `4f2b082ffbcdb055d4043054f252358e98ce6b8c7739e9e075f9d28f93578218` |
| Resolved config SHA-256 | `d3d435c20016884fdd300935c2ceea1041670605c5dc3146bfd70ec93a423df3` |
| Expanded footprint | `0x00008000..0x005adde8`, below 16 MiB |
| Header / load / entry | `0x01ffffc0` / `0x02000000` / `0x02000000` |

The actual ten manifest files were checked against their lengths and SHA-256
before and after local export. Built driver/helper sources match the
authoritative overlay and regenerated patch. This is one embedded-initramfs
payload with no external initrd; low-256-MiB DDR and the low-16-MiB reservation
remain unchanged. Logs and binary artifacts stay outside Git.

## Hardware boundary

The [physical read-only audit](usb-audit-board-20261013.md) measured exactly
CRG46 `0x0013707f`, CRG47 `0x00000b01`, USB0 `0x000c71a8`, USB1 zero and SYSID0
`0x37980100`. This experiment requires all five values before any write or
controller read. An active controller, another board, changed resource or
changed initial bit denies the experiment.

The existing SDK-differentially tested host0 helper performs fixed volatile
clock/PHY initialization. Readback must establish readiness before reading
only EHCI CAPBASE/HCSPARAMS/HCCPARAMS and OHCI revision. Structural checks
validate EHCI length/version/ports and OHCI version, and reject absent/all-ones
capabilities. Success and failure both execute SDK last-user shutdown and
check stopped controls. Expected stop is CRG46 `0x0010000e`, CRG47
`0x00000f03`, USB0 `0x000c71a8`, USB1 `0x0000a801`.

Shutdown does not restore inherited analog PHY tuning. This is a volatile
control-writing experiment. USB_SUPPORT, HCDs, networking, storage, modules,
SMP and debugfs are disabled. There is no controller operational-register,
schedule/DMA, PORTSC, endpoint, firmware or fuse access. The separate host
enumeration image remains denied by the RAM preparation gate.

## Completed local checks

- The actual helper passes ASan/UBSan for all 160 single-bit initial-state
  mutations, foreign active state, both accepted OHCI versions, invalid
  capabilities, stuck initialization and failed shutdown. MMIO addresses,
  capability read order, control-only writes and bounded delays are checked.
- The actual extracted platform probe passes ASan/UBSan for board identity,
  every missing/wrong-sized/wrong-address resource, an extra resource, each
  mapping failure and experiment error propagation.
- Compiled DT/config and mutation checks require the exact isolated profile,
  rejecting the actual `TY1208Z_USB_HOST0_EXPERIMENT` provider option in both
  built-in and module forms. The actual artifact passes the common guarded
  RAM plan, CRC, layout and single-payload bounds.
- Core `make lint`, `make build`, `make test` and serial PTY checks pass.
  The separate candidate builds and passes generic ARM QEMU shell/time64.
  Later collector checks reject missing capabilities and failed stop readback
  even when a completion marker is present. QEMU does not emulate MV100 USB.

Required local markers are `USB_CLOCK_AUDIT_HELPER_PASS`,
`USB_CLOCK_AUDIT_PROBE_PASS`, `USB_CLOCK_AUDIT_RAM_PLAN_PASS` and
`QEMU VIRT PASS`. Diagnostic CI
[38364481882](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38364481882)
passed on `f7e9a615b79713e9c76a444cdbce1fd93797824c`, including the new
independent profile. All twelve downloaded manifests and 119 listed files
were verified by actual length/SHA-256, with eleven uImage CRC/structure
checks and matching Git Wi-Fi patches. The actual USB log contains all four
markers; its SHA-256 is
`1759c8cae95c459e6f2c24935f486a516a5bb1e7b6a5753704b7518d537ebf80`.
The downloaded USB image also passes the exact config/DT/CRC/layout RAM gate
and mutation tests; its actual QEMU console contains the time64 marker.
This remote build predates the later association-frame parser change and
does not establish physical USB acceptance.

## Next physical acceptance

Back up current RAM configuration, collect a fresh CA bootloader inspection,
recheck DDR/bootcmd, receive the exact image and verify its device CRC while
restoring temporary loader network settings. Then collect initial controls,
actual capabilities, verified shutdown and ordinary UART/timer/time64 output.
Review those measurements before considering the separate HCD enumeration
profile. Return to the separately validated router image afterwards.
