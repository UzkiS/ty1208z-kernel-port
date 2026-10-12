# RDA control-response regression, 2026-10-12

The complete optional USB module links after replacing its control-response
parser and completion loop. This fixes software defects in the pinned driver;
no module has been loaded or Wi-Fi operation demonstrated on TY1208Z.

## Defects and resulting behavior

- WID parsing previously read the ID before checking that two bytes existed,
  checked several payload bounds after access and incorrectly required a
  SHORT length of one. The replacement checks each header before access,
  enforces CHAR/SHORT/INT widths, checks BIN bounds/checksum and clears output
  fields on failure. Standalone two-byte query records remain supported.
- The response envelope previously trusted firmware-declared lengths and
  exposed offsets into stale/truncated data. It now checks actual receive
  length, packet/message length agreement, response type, parsed payload
  extent and command ID. USB padding outside the declared packet is allowed.
- The receive completion loop could wait indefinitely on unrelated IDs and
  inspect an old request ID after a short receive. It now checks the actual
  length first, handles ID wraparound by equality and stops after RETRIES.
- USB receive previously copied the smaller of capacity/response length but
  returned the larger original length. Oversized responses are now rejected
  without a partial copy. RX dispatch checks the source header/frame and
  control-buffer capacity before accessing/copying a response.

## Exact local artifact

| Item | Value |
|---|---|
| Kernel release | `6.12.112-ty1208z-wifi-port` |
| Module bytes | 341452 |
| Module SHA-256 | `3c21197f5d1b288eb60a714143866bc00cd245a22c8316598a37868eb115e7df` |
| Patch 0004 SHA-256 | `fa080bab5bbd26b1c1e28761bb8f07c07a9d84b45ada53dfa444ad5c691cc808` |
| Configuration SHA-256 | `0f2d638059c01eb4f91a0ed647ad81114f3cff109ae8359ab72474ee881ede08` |

This supersedes the initial module artifact identity in the earlier module
report. Pinned driver/kernel sources are unchanged. Independent configuration,
ARM ELF/vermagic/USB alias and manufacturing-symbol checks pass.

## Validation and limits

`make wifi-port` runs `test_wifi_control.py` in addition to the existing
key/manufacturing regression. The test compiles the actual patched WID parser,
envelope parser, completion function and USB receive function with ASan/UBSan.
WID classification constants and protocol structures come from the locked
source; bus/USB synchronization and hardware are mocked.

The regression exercises exact-length allocations for every shorter prefix
of valid CHAR/SHORT/INT/STR/BIN records, invalid lengths, unknown IDs, bad
checksums, truncated/inconsistent envelopes, response WID/type mismatch,
successful/failed firmware status, padded receives, short/oversized/error bus
receives, bounded unrelated IDs, 255-to-0 ID wraparound and USB capacity
rejection without destination mutation. RX-dispatch checks are source-order
gates; the entire dispatcher/data path is not emulated by this harness.

Local lint, full module compilation/link, normal diagnostic kernel build,
QEMU time64 and RAM-boot protocol regressions pass. CI for the preceding
`a03fc85` completed successfully; these additional control changes require
their own CI result.

Vendor key deletion/AP stop and empty legacy iovar callbacks remain unresolved.
The work does not claim complete cfg80211 behavior, data-frame parsing,
firmware compatibility, scan, STA/AP, native routing or whole-system Y2038.
