# RDA scan-result parsing and ownership, 2026-10-13

The legacy NETINFO parser had no actual receive-buffer length. It read fixed
headers before establishing their presence, subtracted untrusted WID/frame
lengths and walked IEs without checking each element's complete extent. Its
SSID helper wrote a terminating byte after a full 32-byte destination, and
extended rates were appended with a one-byte gap and inconsistent bounds.
The event callback leaked allocated IEs when dropping results or when
allocating a new list entry failed.

## Changed behavior

A shared project header validates the actual event length, message/WID
envelope and minimum MAC frame before RX dispatch accesses a network frame.
The scan parser receives `e->datalen`, separately requires a complete beacon
or probe-response fixed body and validates every IE before allocating or
publishing a BSS. Invalid message types, WIDs, DS flags, duplicate/oversized
SSIDs and malformed channel/TIM/HT elements fail explicitly. Transport
padding outside the declared message remains permitted.

The parser preserves the caller's output on every failure, including allocation
failure. Full 32-byte SSIDs use their length and bounded logging; no extra
terminator is written. Supported/extended rates are contiguous and capped by
both the declared rate limit and actual array capacity. No firmware capability
reply or named-iovar mapping was introduced; WMM/HT flags still describe
received BSS IEs, not the board's own radio capabilities.

The event callback checks missing interface/configuration pointers, propagates
parser errors and rejects a null success payload. Temporary IEs are freed on
discard/allocation-error paths. A successful new entry or duplicate update
explicitly transfers ownership to the list; the existing entry's old IE buffer
is released before replacement. Completion-only events retain their existing
wait/wakeup and reporting sequence.

The vendor `MAKE_WORD16` macro lacks outer expression parentheses. The new
comparison sites wrap it, and the sanitizer extracts the actual locked macro
definition instead of substituting a differently parenthesized fixture.

## Local acceptance and limits

`test_wifi_scan_results.py` compiles the real shared header, parser, BSS allocator,
duplicate-update function and scan event handler under ASan/UBSan. The actual
RX entry checks are also extracted and executed; later RX dispatch/association
branches are excluded. Tests cover exact short buffers, both complete 16-bit
length-field ranges, message/WID/subtype failures, truncated IE headers/bodies,
all SSID lengths from zero through 32, hidden results, beacon/probe response,
padding, contiguous/large rates and allocation failures without partial output.

The real event callback is exercised for unavailable interfaces, malformed
results, every existing discard category, allocation failure at both stages,
successful insertion, twenty duplicate updates and completion/wakeup ordering.
Allocation tracking and ASan check leaks/double frees; list/lock balance and
maximum-RSSI preservation are asserted. Marker: `RDA_SCAN_RESULTS_PASS`.

Kernel allocation/list/timer/readiness/P2P/reporting dependencies are host
fixtures. This does not establish asynchronous teardown safety, scheduled
scan/association parsing, USB firmware transactions or radio output. The
named-roaming/PHY transport [startup blocker](wifi-startup-20261013.md) remains.

All previous WID/control/key/operation/startup/scan sanitizers and the final
ARM module link/modpost/identity gates passed. `make lint`, `make build` and
`make test` passed locally, including core QEMU time64 and RAM-boot/TFTP
regressions. No image/module was loaded on the TY1208Z. Remote acceptance
of these result-parser changes is pending.

| Local item | Identity |
|---|---|
| Kernel release | `6.12.112-ty1208z-wifi-port` |
| Module bytes | 338996 |
| Module SHA-256 | `d4159a964e2026157fc4c7174d0a807b2e23dec5183a6ea06f1f7ac131c433dc` |
| Generated port patch bytes | 96787 |
| Port patch SHA-256 | `887ed779b8e79d0c2c6456e515e1e94bf5647a539dbface4157b30e4ea8ff8f2` |
| Kernel config SHA-256 | `0f2d638059c01eb4f91a0ed647ad81114f3cff109ae8359ab72474ee881ede08` |

This supersedes the earlier local [scan-dispatch module](wifi-scan-20261013.md)
identity. Remote/local artifacts remain distinct and must match their exact
kernel/config; none is evidence of usable board Wi-Fi.
