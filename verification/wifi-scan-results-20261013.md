# RDA 扫描结果解析与所有权（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

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
of these result-parser changes subsequently passed in the run recorded below.

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

## Remote parser acceptance

[Run 38313816693](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38313816693)
completed successfully on `e52cfb5f2689ef336b9e59cb8cbbc21c67ad3c2b`.
The job ran from 21:57:26 to 22:26:22 UTC on 2026-10-12; every step was
inspected and passed, including all independent diagnostic profiles and upload.
The downloaded Wi-Fi artifact's six manifest files matched their lengths and
SHA-256 hashes. Its port patch matches `887ed779...`, and the actual build log
contains all six control/key/operation/startup/scan/result sanitizer markers.

The remote module is 339124 bytes, SHA-256
`df59a0773395fedabe5bc058a7c6174db226cfa93bbfe6846ac906dd5df0f5c7`;
the Wi-Fi build log SHA-256 is
`49b9c278cfa549996ff94724877fa4e7884604686ca0c1504ee2f07eaf5f8c4c`.
It has the same standalone kernel release, but remains a distinct compiler/build
artifact from the local module above. The later native-OpenWrt package and
strict declaration/linkage changes are excluded from this run. No physical
Wi-Fi or USB initialization is established.
