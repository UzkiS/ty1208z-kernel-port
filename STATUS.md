# TY1208Z kernel port status

Updated: 2026-10-12. Existing Hinas booted; a read-only SSH baseline was collected.
No flashing, persistent boot changes or OTP writes were performed by this project. Offline
implementation and repository push are authorized.

Target: modern Linux, native OpenWrt/Kwrt, Passwall, board Wi-Fi and verified
time64 behavior. The current milestone is a RAM-only, single-core diagnostic.

| Stage | Result |
|---|---|
| Original firmware/source audit | Completed offline; file identities, DTB and pinned SDK references recorded |
| Exact Hinas 4.4 source rebuild | Not performed; exact ecoo source unavailable; vendor reference is not equivalent |
| Linux 6.12.112 candidate | Cross-compiled; board descriptor, UART/GIC DTB, single-core timer and embedded initramfs |
| Structural checks | Passed: CRC, ARM uImage/zImage, appended DTB, static ARM ELF, required/disabled config |
| QEMU virt | Passed: same raw zImage + initramfs; shell, 2040 clock read/write, RAM file times and BusyBox stat |
| GitHub CI | Passed for code commit `a4adc78`: serial PTY tests, collector LF/CRLF regression, PowerShell syntax, clean kernel build and QEMU time64; [run 38199621273](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38199621273) |
| Existing Hinas SSH baseline | Complete: Ubuntu 24.04.4 armhf/glibc 2.39, original 4.4 kernel, four CPUs, 1 GiB reported RAM and current eMMC layout |
| Serial CLI | Original-board boot captured at 115200 8N1, 106675 bytes; guarded inspection added, two physical interrupt attempts unsuccessful and zero query commands sent; see [inspection record](verification/bootloader-inspection-20261012.md) |
| Original Hinas TTL boot | Complete from Boot ROM to login; bootloader and allocation evidence recorded in [TTL report](verification/ttl-boot-20261012.md) |
| Candidate boot on physical TY1208Z | Not attempted |
| CA authentication / RAM placement | Original boot reports secure boot disabled and accepts existing ordinary uImage; candidate authentication, usable RAM and placement remain unverified |
| Hinas startup under new kernel | Not tested; eMMC driver and legacy modules need separate work |
| Wired network / storage / USB / SMP | Not integrated into this minimal diagnostic image |
| Wi-Fi | RDA USB `1e04:8888`, vendor interface FF/FF/FF, no bound driver; matching modern driver and exact chip revision remain unverified |
| OpenWrt/Kwrt / Passwall | Planned; no working target or router image yet |
| Whole-system Y2038 | Not established; diagnostic time64 passed, application-level testing remains |

Known-successful CA bootloader SHA-256:
`f891870ec98b4df48de879afc1e1973cf14cc9057eb18a5a41d974fab3e935bc`.

The candidate is an ordinary unsigned uImage, not ADVCA packaged or ready to
flash. Header load/entry is copied from local Hinas, not a validated RAM map.
Initial DTB memory is a 256 MiB placeholder with no verified secure reservations.

Original TTL boot now identifies Fastboot 3.3.0-dirty, 1GB DDR, the existing image
load path and 11 boot-time allocations. Next physical step: inspect current
bootloader commands and clarify RAM/DTB constraints. SSH and TTL still do not
establish a safe candidate load map. Only then choose a real temporary-boot
method and adjust candidate. RDA driver source/firmware assessment
continues independently; the installed Realtek modules do not match this device.

Current console issue: isolated CR and CRLF tests returned only the transmitted
bytes; the user reports a login prompt on Enter in HiTool. Saved port settings
match. Resolve this discrepancy before arranging another bootloader interrupt.
Local bootargs contains `bootdelay=0`; live environment remains unqueried.

The first Windows collection reached its END marker but exited 127 because
PowerShell appended CRLF to the script. The collector now exits explicitly and
passes local LF/CRLF transport regression. The saved hardware report is usable;
raw logs and runtime FDT stay in ignored local evidence. Anonymized measurements
are in [verification/baseline-20261012.md](verification/baseline-20261012.md).

See `docs/hardware.md`, `docs/wifi.md` and `docs/validation.md` for evidence and
limits. No flash commands are provided at this stage.

Serial collection now uses [the CLI workflow](docs/ttl-baseline.md), without
HiTool for routine UART access. Local validation is recorded in
[verification/serial-cli-20261012.md](verification/serial-cli-20261012.md).
