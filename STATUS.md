# TY1208Z kernel port status

Updated: 2026-10-12. Existing Hinas booted; a read-only SSH baseline was collected.
No flashing, persistent boot changes or OTP writes were performed. Offline
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
| GitHub CI | Passed for code commit `0f9332f`: collector LF/CRLF regression, PowerShell syntax, clean kernel build and QEMU time64; [run 38188649931](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38188649931) |
| Existing Hinas SSH baseline | Complete: Ubuntu 24.04.4 armhf/glibc 2.39, original 4.4 kernel, four CPUs, 1 GiB reported RAM and current eMMC layout |
| Serial CLI | RX-only tool opens the local CH340 at 115200 8N1; six Linux PTY integration tests passed; complete early boot capture still pending |
| Candidate boot on physical TY1208Z | Not attempted |
| CA authentication / RAM placement | Unverified; DT memory range and load address require hardware confirmation |
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

Next physical step: capture normal boot over TTL, current bootloader capabilities
and actual RAM/security constraints. SSH established the Linux-reported RAM and
five FDT reservations, not a safe bootloader load map. Only then choose a real
temporary-boot method and adjust candidate. RDA driver source/firmware assessment
continues independently; the installed Realtek modules do not match this device.

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
