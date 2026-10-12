# Complete diagnostic CI acceptance, 2026-10-13

[Run 38300887226](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38300887226)
completed successfully on `7bad0897e9caabfa6d9ea1c0697dcc18e98ace34`.
The diagnostic job started at 19:56:14 UTC and completed at 20:24:51 UTC
on 2026-10-12. The actual Actions job and every step were inspected.

The fresh runner passed repository/script checks, serial PTY integration,
the PowerShell collector parse, pinned Linux/BusyBox compilation and ARM
time64 regression. Independent eMMC register, identification and fixed-sector
profiles built and passed their policy/content/QEMU checks. Ethernet audit,
temporary clock/PHY-ID and inherited-PHY datapath profiles passed their
corresponding software checks.

The separate RDA module linked and passed manufacturing/key/operation guards.
USB shared clock/PHY differential checks, the offline host0 enumeration image
and deliberate RAM-boot refusal, the read-only USB register profile and the
isolated SP805 restart profile all passed. Diagnostic artifacts and logs were
uploaded as hardware-untested candidates.

This establishes the full remote result for source-download recovery and the
Wi-Fi operation changes through `7bad089`. The later `cb2b5b8` READY rollback
has local real-function sanitizer/link acceptance; this run does not contain
that change. Application UDP/NTP fixtures have a separate workflow and are
not accepted by this result.

The job did not access the TY1208Z. No new USB, Wi-Fi, native OpenWrt,
restart, storage or physical performance result is implied. Earlier
`c25f83d` diagnostic run 38298432030 was cancelled by the `7bad089` push,
after passing download/build/core checks; it is not a complete acceptance.

## READY rollback accepted remotely

The later [run 38304430531](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38304430531)
completed successfully on `fbc1e792b2cf7adfabad70e41521760bead20f06`.
It includes `cb2b5b8` and the actual RDA startup rollback harness, not just
the earlier operation guards. The full diagnostic job and all independent
profiles completed again. Wi-Fi hardware initialization remains blocked by
the missing named-roaming/capability transport. This run predates the new
TFTP CLI and cannot establish acceptance of that later tool.

## TFTP RAM transport accepted remotely

The later [run 38307787289](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38307787289)
completed successfully on `164fc1801e814aa33b9c7b24b284b5251aa7dab7`.
The diagnostic job ran from 20:59:41 to 21:18:14 UTC on 2026-10-12;
the actual job and every step were inspected and succeeded.

This includes the real UDP/curl TFTP protocol tests in serial integration,
the UART PTY size/CRC/environment-restoration gates, pinned core build and
QEMU/time64 regression, all independent eMMC/Ethernet/USB/restart profiles,
RDA module guards and artifact upload. The previously accepted READY rollback
is included. The later directed-scan and bounded-SSID logging changes in
`67d2a8b` and `8be80e0` are not included in this run.

This is remote software acceptance. Physical TFTP, native OpenWrt startup,
sustained Ethernet traffic and Wi-Fi remain unverified. Application UDP/NTP
checks belong to their separate workflow and are not established by this run.

## Directed-scan dispatch and logging accepted remotely

The later [run 38310319501](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38310319501)
completed successfully on `9e5bd2b68a7681c3a0d5fa6b7d3003d459c1cc77`.
The diagnostic job ran from 21:23:24 to 21:51:56 UTC on 2026-10-12;
the actual job and every step succeeded, including all independent profiles
and artifact upload. This establishes remote acceptance of the directed-scan
failure/early-completion and formatted-SSID logging fixes through `8be80e0`.

The downloaded Wi-Fi artifact's six manifest files were verified by length
and SHA-256. Its patch matches the recorded scan-dispatch version, and the
actual build log contains standalone `RDA_SCAN_FAILURE_PASS`,
`RDA_STARTUP_ROLLBACK_PASS` and `RDA_CONTROL_PASS` markers. The later
[result-parser changes](wifi-scan-results-20261013.md) are excluded from this
run. Physical Wi-Fi/native OpenWrt and application UDP/NTP acceptance remain
separate and unestablished by these diagnostic checks.
