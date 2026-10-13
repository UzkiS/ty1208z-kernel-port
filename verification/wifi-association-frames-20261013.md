# RDA STA/AP association-frame parsing

Date: 2026-10-13. Source, actual-function sanitizer and standalone/native
compile acceptance only. USB enumeration, firmware, scan, association and AP
on the TY1208Z remain unverified.

The original `wland_get_assoc_ies_from_frame()` reads a management header
before checking the received length, subtracts fixed fields into an unsigned
length and frees existing IEs before establishing allocation success.
A short received frame can therefore read beyond its buffer or produce an
underflowed copy length. The new regression executes the actual original
function and reproduces an ASan heap-buffer-overflow; the patched function
passes the same fixtures.

## Resulting behavior

The parser checks the interface/frame, received MAC header, version, subtype
and DS bits before accessing body fields. It retains the locked source's
optional HT-control header rule and bounds the request/response fixed fields
before subtraction. It validates every IE and rejects overlong SSIDs and
invalid HT capability sizes before allocation or state changes.

IE storage uses atomic allocation for the receive path. Failed validation or
allocation leaves prior IEs intact. A new AP station enters the list only
after both its IE copy and station allocation succeed; allocation failure
releases the temporary copy. Request replacements clear stale WMM/HT flags,
while valid empty IE streams clear the prior pointer/length. Existing station
TID history is retained. Receiver dispatch returns the parser error and the
optional soft-MAC association analysis runs only after parsing succeeds.

This preserves the existing request/response formats. Reassociation frames,
the separate WID association-IE getter, AP connection-event payloads and
concurrent teardown/notification ownership are separate work; this change
does not establish them.

## Actual validation and artifacts

The test executes the real parser and its actual TLV/WMM helpers under
ASan/UBSan. Both STA response and AP request paths cover all short MAC/fixed
headers, optional HT-control headers, every incomplete IE prefix, malformed
fields, wrong subtype/version/DS bits, replacement/empty IEs, prior-data
preservation, station allocation failure, lock balance and allocation cleanup.
The actual original parser fails with a heap-buffer-overflow rather than a
test-only substitute. The patched standalone and native package sources both
contain the authoritative replacement and pass `RDA_ASSOC_FRAMES_PASS`.

The complete standalone module and native OpenWrt APK rebuilt. Native kernel
ABI, real APK metadata/payload, built-in symbol providers and equality to the
stripped linked module passed, including eight deliberately broken real APK
cases. All six standalone and seventeen native manifest files were verified
by actual length/SHA-256 before and after local export. Lint, core build and
QEMU time64/RAM-boot protocol regression also passed.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Standalone `rdawfmac.ko` | 320120 | `2f801a29984f27eb4a1f4a436e80c1078ed216ccba4a66faa3b22ca814626946` |
| Native linked module | 5972124 | `3a7c0293f22da71d4246c5dc810570b54c1d477555642e01cced559523e32054` |
| Native packaged module | 353244 | `832942b70c2b8e3ce660308254c2f2ded888e1cbbb5421ff679e0d739356d0fc` |
| Native APK | 139270 | `7b24488cd0c4e7f2889686a721249ddef31b6bf6b276790f7e6f6206582d6a1f` |
| Generated port patch | 125569 | `86ce677246013469586aa611ea4548c5e7e6736452f01356312b49cd172b7a57` |

Native vermagic is `6.12.112 mod_unload ARMv7 p2v8`; kernel ABI is
`6.12.112~d16c03293ab72d701652b784b169e892-r1`. There is no firmware payload,
automatic module loading or boot-image export. No module was loaded on the
box. Named roaming/capability startup transport remains unsupported; passing
these tests does not bypass that blocker or prove working STA/AP.

Both build entries now run this additional sanitizer. The native entry
selects the actual package source and matching Linux tree after compilation,
and rejects missing or ambiguous trees before export. Changes to Wi-Fi
sanitizer scripts also trigger the native package workflow. Remote results
for the native package entry remain pending. The later standalone diagnostic
[run 38374147701](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38374147701)
passed on `45762c2`; all six Wi-Fi manifest files, both exact Git patches and
the actual `RDA_ASSOC_FRAMES_PASS` marker were independently verified. See
the [complete CI report](diagnostic-ci-latest-20261013.md). This does not
replace native-package or physical radio acceptance.
