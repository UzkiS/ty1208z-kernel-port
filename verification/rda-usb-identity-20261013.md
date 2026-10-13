# Fixed RDA USB identity queries

The user reported the visible chip marking **RDA5995** on 2026-10-13. This is
a user observation, not an independently photographed or protocol-derived
identity. USB `1e04:8888` and `bcdDevice=0000` alone do not distinguish family
or revision. The separate RAM query experiment and device transactions are
recorded below; no storage or persistent boot state was changed.

`tools/rda_usb_identity.c` provides only `--selftest` and explicit `--probe`.
The latter checks the exact enumeration-kernel release/board compatible,
USB 1-2 identity, speed/configuration and unbound interface. It validates both
sysfs and the opened usbfs descriptor stream before claiming interface zero.
The exact measured 71-byte descriptor stream, with five bulk endpoints, is
required. The pinned driver selects the first OUT/IN pipes, `01/82`, whose
maximum packets are 512 bytes; the additional `03/83` pair advertises 64 bytes
and `84` advertises 512. There is no endpoint override or kernel Wi-Fi driver.

The fixed source `ef379d496bc0cd4b7bbeced783245f5e450a506d`,
`rdawlan/wland_cmds.c` (`wland_wid_hdrpush`, `wland_proto_cdc_msg`) and
`wland_wid.h` establish the eight-byte request: little-endian `0x4008`, `Q`,
sequence, little-endian message length six, and little-endian WID.
`wland_usb_send_ctl` sends requests of this size without download padding.
Only these existing `wland_start_chip` query IDs are exposed:

| WID | Data | Interpretation limit |
|---|---|---|
| `201e` (`WID_MEMORY_ADDRESS`) | Exactly four bytes | The source treats `ffffffff` as firmware already running; other values do not identify a chip family |
| `0416` (`WID_CHIP_VERSION`) | Exactly one byte | Revision only; source-selected `WLAND_VER_91_H` is not measured family evidence |
| `3001` (`WID_FIRMWARE_VERSION`) | One to twenty bytes | Raw device bytes; unsupported before firmware startup is possible |

Replies must match both length layers, response packet/message type, sequence,
WID and typed size before data publication. A successful WID_STATUS ack is
reported as absent identity data rather than accepted as a queried value.
Each request has a 500-ms send timeout, a two-second total monotonic budget and
at most five receives for stale sequence replies. All calls release the claim
or close the descriptor. There are no firmware/memory writes, arbitrary query
arguments, USB reset/configuration/control ioctls, or radio commands.

## Offline and physical evidence

The actual C parser and actual main/query/device-check functions pass host
ASan/UBSan. Tests cover all 65,536 requested WIDs, exact-allocation truncated
responses, descriptor mutations, 30,000 arbitrary inputs, unsupported/busy
devices, changed opened descriptors, claim/release failures, short/error sends,
timeouts, five stale replies, eventual matching reply, malformed replies and
status-only acknowledgements. Every mocked ioctl asserts that it is either
claim/release or a fixed query/read bulk transfer. `--selftest` and invalid
arguments assert zero device access.

The USB-host build packages a static ARM binary, runs its selftest in qemu-arm,
and runs only its device-free selftest during the isolated QEMU kernel boot.
Normal board startup never sends a query automatically. Core `make lint`,
`make build`, `make test`, actual syscall/parser sanitizers, ARM user selftest,
updated USB candidate build, exact profile/RAM mutations and kernel QEMU
time64/selftest passed locally. The final 2477332-byte offline uImage SHA-256
is `f9e181a12a05d318b912261f0d93f2b2c3ae9d199b5e3c49686767147e956969`,
CRC32 `1d406c1f`, with physical BSS end `0x6aa750`. Its QEMU console SHA-256 is
`99bf7e32b3ab4863cbc3ef1c8de728dee09bdc0a2f3cf537de59000d7359e261`.
This final packaged image has not booted on the board; the hardware experiment
used the earlier image plus the separately verified RAM executable below.

## Physical query experiment

Fresh original-loader inspection, immutable TFTP receipt, actual filesize and
device CRC `e4230db6` passed for a 2476276-byte query-kernel uImage, SHA-256
`ed001c4408f3e43b29248e453c72fa0c1597fca6ea8f32671f141ce8ae26669a`.
The kernel/USB hosts/RDA booted. The unfinished earlier descriptor guard
expected two endpoints and correctly refused this five-endpoint device without
sending a query. A read-only descriptor capture established 71 bytes and
SHA-256 `5f5019831a73a1d257d5e6769c74f37ab182b56775dd4e4ffc7a562eeb4c08ce`,
which matched the board's own sha256sum. The guard now requires that exact
stream. Source inspection also established the actual first-pipe `01/82`
selection; there was no trial of guessed endpoints.

The corrected source was separately built with the existing native GCC 14.3 /
musl toolchain. The static 33864-byte ARM executable SHA-256 is
`3b34e6bf359de2d2623725baf40c59c6c41b8a9a1a9357365826301b8df8c740`.
It passed actual-function host sanitizers and qemu-arm selftest, then was
uploaded over UART only to RAM `/tmp`. The board's sha256sum matched before
execution, and the real ARM selftest passed. No kernel/module replacement or
additional reboot was needed for this correction.

| Explicit query | Actual USB response | Result |
|---|---|---|
| State `201e`, sequence `a1` | `0d3052a10b001e200400000000` | Valid four-byte zero value |
| Revision `0416`, sequence `a2` | `063052a20400` | Six-byte response header, no WID/data; parser returns `-EMSGSIZE` |
| Firmware `3001`, sequence `a3` | `063052a30400` | Six-byte response header, no WID/data; parser returns `-EMSGSIZE` |

Both length layers, response type and sequence are visible in the raw USB
records. The latter two responses cannot identify a revision or firmware
version. The pinned startup source would enter its download branch for the
state zero value; this is not a firmware-selection or family-identification
proof. Interface release returned zero, and both controllers/root hubs/RDA
remained present. The subsequent RAM-file time64 probe passed without a
physical future wall-clock change.

The complete UART query capture is 1579 bytes, SHA-256
`acd43cd7c2f3a3a20f306e4c0023c3a6ce5f8bcdd8c80cc13993023ce12f8629`.
The corrected executable upload/selftest capture is 187462 bytes, SHA-256
`c736eab42648e4003a98fdb5900b5d70dfcda32f9285e739c494857ec0dd2856`.
Ignored local raw logs and journals preserve the transport evidence. No Wi-Fi
module or firmware was loaded, and no STA/AP or firmware compatibility is
claimed. Matching firmware provenance and the unsupported named
roaming/capability startup path remain to be resolved.

## Restore the Chinese router

After the queries, the user power-cycled once with the serial listener ready.
Fresh loader/RAM inspection, actual two-file TFTP receipts/filesizes/device
CRCs (`9d11beca`, `3ff40518`) and loader-network restoration passed for the
previously accepted Chinese router image. The latest local RAM backup was
6055 bytes, SHA-256
`96e128e243bd7d459a77ac198993af9d22f5285c9ab07738aded0a25ad1aefc5`.
All 15 configuration/password/authorized-key files were restored and verified
on the board. Chinese login and authenticated Passwall pages passed with the
preserved password; DHCP DNS, normal-date NTP, gateway pings and RAM-file
time64 passed. The physical address changed to `10.0.0.100`.

Final health raw SHA-256 is
`ddb1d96342afbb78d60c3f8caae6e3de7a4e572bb1e2b71402861a9520badc14`.
Passwall retains the user's disabled setting, and temporary namespace/test
firewall state is absent. COM9 is released. This restoration does not extend
radio or external-routing acceptance.

## Verified diagnostic CI

[Run 38385651695](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38385651695)
passed on `bd1d76e43319dab66a6a3b1d75304f13632d6b0b`. Downloaded artifacts
match all 120 files in twelve actual manifests; eleven uImages have correct
header/payload CRCs and exactly match their zImage plus DTB. Both shared Wi-Fi
patches match that Git revision, and all nine actual Wi-Fi sanitizer markers
are present. The USB build log includes the actual identity parser/syscall
regression, ARM wire-only selftest, USB helper and QEMU time64 success markers.
Its SHA-256 is
`0a6a1cb34a22d84d1c01a444a96d81c38a2601522aac07fe5947b15c8b58df47`.
These are offline/tooling results; the earlier physical replies and restored
router retain their exact separately recorded image/executable identities.
