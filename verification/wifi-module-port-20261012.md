# RDA USB Linux 6.12 module port, 2026-10-12

The optional USB driver compiles and links as an ARM module against its own
Linux 6.12.112 configuration. This is a software milestone. It has not been
loaded on TY1208Z, and does not establish firmware initialization or networking.
The normal RAM diagnostic remains independent of this module.

## Inputs and local artifact

The driver source is pinned in `reference/wifi-rda-usb.lock.json` to commit
`ef379d496bc0cd4b7bbeced783245f5e450a506d` of the public Realme TechLife Robot
Vacuum kernel repository. Only the 48 locked source/header files are fetched;
firmware is neither fetched nor distributed by this build.

| Item | Value |
|---|---|
| Kernel release | `6.12.112-ty1208z-wifi-port` |
| Module bytes | 343780 |
| Module SHA-256 | `e6b46a31433bfd1aeccaf5c0a9833cb86ef82c9f7c4cfcab7f4d928e483cdb76` |
| Patch 0004 SHA-256 | `f6f39d00ae0c79a23a556d75b163432f05a13b5920322d5e75512f21d1f38878` |
| Configuration SHA-256 | `0f2d638059c01eb4f91a0ed647ad81114f3cff109ae8359ab72474ee881ede08` |
| Observed USB ID / module alias | `1e04:8888` |

The artifact is a relocatable 32-bit ARM ELF with the expected vermagic and
USB alias. Kernel and module modpost complete. These identities apply to the
local build; a CI artifact is not assumed to be byte-identical.

## Validation

`make wifi-port` prepares a separate kernel output tree, generates patches
from hash-checked source, runs the host regression, builds kernel symbols,
links the complete USB module and validates its artifact manifest. A repeated
build restores the locked inputs and removes the project-generated key header
before patch application. CI regenerates the patches and checks for drift.

The host C regression executes the actual patched WID packer and project key
helper with address and undefined-behavior sanitizers. It covers prohibited
eFuse write requests without message mutation, permitted query/normal
requests, exact 5/16-byte key buffers, accepted/rejected key lengths and TKIP
MIC ordering. Source gates also check removal of manufacturing parsers,
test-firmware paths and the premature roaming BSS release.

Private manufacturing entry points and eFuse write implementations are
excluded, and both single and batched WID requests reject their write IDs.
The driver can still read calibration information. Persistent file-write
helpers return `-EOPNOTSUPP`. Debugfs is disabled in this build.

The existing diagnostic build and QEMU time64/RAM protocol regressions passed
after this integration. Full module CI results are recorded separately in
`STATUS.md` once the corresponding run finishes.

## Remaining work

USB host/PHY support on this SoC, exact Wi-Fi chip revision, suitable firmware,
firmware licensing, cold initialization, scan, encrypted association, DHCP,
throughput, reconnection and AP behavior remain unverified. Some vendor
callbacks, including key deletion and AP stop, require further behavior review.
Vendor missing-prototype and unused-helper compiler warnings remain visible.
No claim of a working STA/AP, router image or complete Y2038 solution is made.
