# Diagnostic CI after USB board acceptance and association bounds

GitHub Actions [run 38374147701](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38374147701)
completed successfully on `45762c2728dc40e1df323eed512419d9b0615e51`.
The actual artifact was downloaded and independently checked: twelve profile
manifests, all 119 declared files, eleven uImage header/payload CRCs and
load/entry addresses, and each appended zImage/DTB identity passed. Both Wi-Fi
patch files match the exact Git commit rather than a later working tree.

The actual Wi-Fi log contains all nine required sanitizer markers, including
`RDA_ASSOC_FRAMES_PASS`, `RDA_CHIP_START_PASS`, scan/result bounds, startup
rollback, control/key/operation and manufacturing guards. The Ethernet log
contains both probe/helper markers and actual FEMAC datapath/TX ownership
markers. The USB-host build log contains the 2048 SDK sequence comparison,
four actual profile/RAM-permission/mutation tests and QEMU time64 acceptance.
The clock-audit log contains helper/probe/RAM-plan markers and QEMU acceptance.

| Actual downloaded log | SHA-256 |
|---|---|
| Wi-Fi port | `1cb32ea3b9665e92dfe17b1b1011f939444e42f46c81692d90b728cf2af603fc` |
| Ethernet network | `71f52ffb5768409eeef67098f390ccbeca7dfce53d87484523f4d6c1435ddb97` |
| Read-only USB audit | `7875ea01ca6af0980c090cc9c6397d75765ad3259138d7764421c59dceafae26` |
| USB-host image | `2ed31c7fc21b8b0172cfbd7c0066683e5402f8255e1bd4dfadf4fe86412c1e38` |
| USB clock/capability audit | `e8dd7e299cc327aa26c67e272ae91e4b75ca8b0bbc750b1c9357f31f479e104c` |

This verifies remote software builds and regressions. Physical USB
acceptance is recorded separately in the [host report](usb-host-board-20261013.md).
It does not establish Wi-Fi firmware/STA/AP, native package CI, application
CI, external routing or persistent installation.
