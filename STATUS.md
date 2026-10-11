# TY1208Z kernel port status

Updated: 2026-10-11. Device remains off; no device partition, bootloader or OTP
has been modified. Offline implementation and repository push are authorized.

Target: modern Linux, native OpenWrt/Kwrt, Passwall, board Wi-Fi and verified
time64 behavior. The current milestone is a RAM-only, single-core diagnostic.

| Stage | Result |
|---|---|
| Original firmware/source audit | Completed offline; file identities, DTB and pinned SDK references recorded |
| Exact Hinas 4.4 source rebuild | Not performed; exact ecoo source unavailable; vendor reference is not equivalent |
| Linux 6.12.112 candidate | Cross-compiled; board descriptor, UART/GIC DTB, single-core timer and embedded initramfs |
| Structural checks | Passed: CRC, ARM uImage/zImage, appended DTB, static ARM ELF, required/disabled config |
| QEMU virt | Passed: same raw zImage + initramfs; shell, 2040 clock read/write, RAM file times and BusyBox stat |
| GitHub CI | Passed for code commit `7b99fe6`; [run 38141542884](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38141542884) |
| Physical TY1208Z boot | Not attempted |
| CA authentication / RAM placement | Unverified; DT memory range and load address require hardware confirmation |
| Hinas startup under new kernel | Not tested; eMMC driver and legacy modules need separate work |
| Wired network / storage / USB / SMP | Not integrated into this minimal diagnostic image |
| Wi-Fi | In scope; firmware clues and upstream options audited, actual chip unconfirmed |
| OpenWrt/Kwrt / Passwall | Planned; no working target or router image yet |
| Whole-system Y2038 | Not established; diagnostic time64 passed, application-level testing remains |

Known-successful CA bootloader SHA-256:
`f891870ec98b4df48de879afc1e1973cf14cc9057eb18a5a41d974fab3e935bc`.

The candidate is an ordinary unsigned uImage, not ADVCA packaged or ready to
flash. Header load/entry is copied from local Hinas, not a validated RAM map.
Initial DTB memory is a 256 MiB placeholder with no verified secure reservations.

Next physical step: capture normal Hinas TTL/SSH baseline, current bootloader
capabilities and actual RAM/security constraints. Confirm Wi-Fi USB/SDIO IDs at
the same time. Only then choose a real temporary-boot method and adjust candidate.

See `docs/hardware.md`, `docs/wifi.md` and `docs/validation.md` for evidence and
limits. No flash commands are provided at this stage.
