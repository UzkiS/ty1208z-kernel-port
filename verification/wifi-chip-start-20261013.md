# RDA chip startup acknowledgement, 2026-10-13

The locked chip-start function published `chip_ready` before querying the
revision and firmware version. It converted version-query failures to success
and invented revision u04 after a failed query. The replacement keeps READY
clear and preserves the cached revision until both real queries return data.
Negative errors remain visible to the caller and the cold path may be retried.

The firmware-state query requires a complete 32-bit reply before deciding
whether to download firmware. Status-only acknowledgements are rejected as
state/version data. The revision requires one byte; the firmware version
requires a nonzero copied length and uses a 21-byte buffer for the 20-byte
query and trailing NUL. This verifies acknowledged revision data, not the chip
family selected in the USB probe or completion of cfg80211 initialization.

The existing normal-mode firmware sequence and first preinit write are
preserved. Manufacturing triggers remain removed and modes other than exact
`sta`, `ap` and `p2p` are rejected. Existing ready state still returns through
the cached fast path; this is not a new liveness check.

## Actual-function checks

`tools/test_wifi_chip_start.py` extracts the actual replacement, typed getter,
completion routine and both wire parsers. Controlled bus replies exercise
the real query/parsing code under ASan/UBSan. It covers four errors at each
of nine startup stages, stop-at-first-failure ordering, successful retries,
status-only/incorrect-WID/truncated/zero/wrong-ID replies, an empty version,
all 1..20-byte unterminated firmware strings, normal modes, invalid modes,
missing device context and the existing-ready fast path.

Marker: `RDA_CHIP_START_PASS`. Transport, download and configuration helpers
are fixtures; this is not a firmware transfer, calibration or radio test.
The compiled USB path is covered, not the optional SDIO/platform/file-mode
branches. All previous control/key/operation/interface-start/scan/result
sanitizers also pass. `make lint`, `make build` and `make test` pass, including
ARM/QEMU time64 and guarded RAM-boot/TFTP regressions.

## Local builds

The complete standalone ARM module and the separate native OpenWrt APK were
rebuilt. Native kernel/config ABI, USB alias, packaged/linked module equality,
built-in symbol providers and all eight broken-APK cases pass.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Shared generated port patch | 118947 | `489f8b9d231f5e8b40b4344986c82aaf0c1ea8c0619220746549445493cab449` |
| Standalone module | 320880 | `139256a4b0fd96fee84a80f2dd46148306022167bc857e59e82892580497677a` |
| Native APK | 139468 | `11b8652e884783d0d9aac8622aa03250702b9b7aa2a4beabab1ec933d8a4949c` |
| Native packaged module | 354068 | `a5ea0a7a296da739c694d369d3d75d7fa91ca658cc8ae07086f647ce1f9534bb` |

Standalone release remains `6.12.112-ty1208z-wifi-port`. The native release
remains `6.12.112`, with kernel ABI dependency
`kernel=6.12.112~d16c03293ab72d701652b784b169e892-r1`. These modules are
not interchangeable. This identity supersedes the earlier local package
report; fresh CI for this chip-start change is pending.

No driver was loaded on the board. USB enumeration, real revision/firmware,
named roaming/capability transport and radio acceptance remain outstanding.
The real unsupported cfg80211-startup regression still reproduces its
initialization blocker. No hardware/storage/security-state writes occurred.
