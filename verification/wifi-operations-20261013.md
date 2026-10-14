# RDA 不支持操作与 AP 停止顺序（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The later [startup rollback report](wifi-startup-20261013.md) supersedes the
module identity below and records the active initialization blocker.

The locked driver contained named-iovar functions with their entire transport
disabled by `#if 0`, but returned success. Key deletion also returned before
its request, and primary-interface AP stop returned success without a command.
The optional Linux 6.12 USB port now reports these missing operations explicitly.
This is software correctness work; no module or firmware was loaded on TY1208Z.

## Resulting behavior

- Named-iovar get/set return `-EOPNOTSUPP`, leave caller buffers untouched and
  issue no firmware transaction. No mapping from these names to RDA WIDs was
  guessed or borrowed from a different chipset.
- Key deletion, key retrieval and default-key selection return unsupported for
  valid requests. Invalid key slots, absent retrieval callbacks and down
  interfaces return errors. Retrieval never invokes cfg80211's callback with
  empty or inferred key material. Management-key selection remains unsupported.
- AP stop rejects unsupported roles/interfaces, inconsistent role descriptions,
  invalid interface addresses and nonzero links. Only the existing pinned
  `P2PAPI_BSSCFG_DEVICE` / `WID_STOP_AP_MAC1` six-byte MAC request is retained.
  Its firmware errors propagate without changing the AP state. A successful
  reply preserves the original configured-role transition: `AP_CREATING` set,
  `AP_CREATED` clear. Primary-interface AP shutdown still needs implementation.
- BIP/AES-CMAC and WAPI/SMS4 are removed from the advertised cipher list because
  their key callbacks have no supported command path. The remaining declared
  WEP/TKIP/CCMP paths are source-level candidates, not firmware/radio acceptance.
- Failed TX-power requests do not update the driver's cached power. Reading
  unsupported TX power leaves the output untouched; its error log no longer
  dereferences an output that has not been assigned.

Named-iovar errors may now expose previously hidden failures in other legacy
callers, including initialization and optional features. Some callers ignore
those errors and still require audit. Returning an error does not implement the
operation or establish usable association/AP/reconnection. In particular, key
removal is required work before production use; no invented removal payload or
implicit local success is supplied.

## Actual-function verification

`tools/test_wifi_operations.py` extracts the compiled port's actual named-iovar,
key-deletion/retrieval/default-key, TX-power and AP-stop functions. Interface,
state, BSS-index and command constants come from the locked vendor source;
cipher and nl80211 enums/macros come from pinned Linux 6.12.112. Kernel object
plumbing and the AP-stop firmware transport are mocked. TX-power conversion is
mocked only to exercise the actual unsupported transport/error path.

ASan/UBSan checks all 256 key slots, both pairwise choices and all Linux
interface roles; checks unchanged caller buffers with ordinary, oversized and
null named-iovar arguments; verifies no key callback or firmware request for
unsupported operations; and verifies the real AP-stop payload, pre-reply state,
negative firmware errors and positive success returns. Unsupported TX-power
reads and writes preserve output/cached state. The actual advertised cipher
array and its wiphy binding are checked. Marker: `RDA_OPERATIONS_PASS`.

Existing actual WID/control/PTK/GTK sanitizer checks also pass. The complete
optional ARM module links and passes modpost, ELF/vermagic/USB-alias and
manufacturing-symbol checks. New replacement snippets pass pinned-kernel
checkpatch with zero errors/warnings. Existing vendor unused-function and
missing-prototype warnings remain. Repository lint, cached diagnostic build,
core QEMU/time64 and guarded boot tests passed locally; remote acceptance of
this change remains pending.

## Latest local identity

| Item | Result |
|---|---|
| Kernel release | `6.12.112-ty1208z-wifi-port` |
| Module bytes | 339208 |
| Module SHA-256 | `cac8e16c5b4d4fc4b42e455d28d77c2bf2898cdbf8196b782963cbc6d370dbbd` |
| Port patch bytes | 80474 |
| Port patch SHA-256 | `d4bc91ac1b2126d2ca7316e097175d153cd7df8372d4760971f0a36348d71f8b` |
| Kernel config SHA-256 | `0f2d638059c01eb4f91a0ed647ad81114f3cff109ae8359ab72474ee881ede08` |

This module supersedes the earlier key-callback artifact. It must match its
exact kernel/config; the current board diagnostic does not provide USB/modules.
USB controller operation, chipset revision, firmware, scan, association, AP,
DHCP and radio performance remain physically unverified.
