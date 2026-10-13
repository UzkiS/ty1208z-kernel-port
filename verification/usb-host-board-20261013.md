# USB host0 and RDA physical enumeration

Date: 2026-10-13. The exact independent `usb-host1` RAM candidate booted on
TY1208Z following the [physical capability audit](usb-clock-audit-board-20261013.md).
EHCI/OHCI startup, root hubs, RDA descriptors and shared-clock lifetime passed.
There is no Wi-Fi driver, firmware or radio acceptance in this image.

The 2247932-byte uImage SHA-256 is
`8f32dd5961f231819c6c430c5a8869f4566c3ed207bea0f87b6884d8cd52e299`;
device CRC32 `cad54a66` matched the host before boot. Fresh bootloader/DDR
inspection and immutable TFTP receipt passed. Loader network settings were
restored, and storage/class/network drivers, modules and SMP remained disabled.

| Physical observation | Result |
|---|---|
| EHCI `f9890000.usb` | `ehci-platform`, GIC hardware IRQ 98 (SPI 66) |
| OHCI `f9880000.usb` | `ohci-platform`, GIC hardware IRQ 99 (SPI 67) |
| EHCI root hub | `1d6b:0002`, 480 Mbps |
| OHCI root hub | `1d6b:0001`, 12 Mbps |
| Onboard device at port 2 | `1e04:8888`, 480 Mbps, bcdDevice `0000`, one configuration/interface |
| Memory / time64 | 244476 KiB; eight-byte time_t, RAM timestamp `2208988800` |
| Timer / GIC | 6383 -> 6485 interrupts over one second; Err=0 |

The RDA still advertises 64-byte high-speed bulk maximum packets on `03/83`.
Linux reports those invalid descriptors, as the original Hinas log did.
No descriptor override was added. USB enumeration does not determine chip
revision or establish that firmware/data transfers will work.

## Shared-clock lifetime on the actual board

Fixed driver-sysfs unbind/bind operations exercised both consumers without
touching storage. Removing OHCI left EHCI and RDA present with no extra clock
prepare/stop. Rebinding OHCI restored its root hub. Removing EHCI left OHCI's
root hub present and removed the high-speed RDA, without stopping the shared
clock. Removing the last OHCI consumer produced exactly one successful
`USB_HOST0_STOPPED last-ccf-user`.

Rebinding EHCI produced the second successful prepare and re-enumerated RDA.
Rebinding OHCI restored both hubs without another prepare. Seven stages
passed; final totals were two prepares and one stop, no prepare/shutdown error,
both hubs and RDA present, and another successful time64 probe.
This covers ordinary companion removal/rebind and last-user shutdown;
injected hardware failures and system-shutdown behavior remain separate.

| Local evidence | Bytes | SHA-256 |
|---|---:|---|
| Fresh inspection | 2491 | `9669c93e444d69dc4b332653fc9c93e45584a2ab2a3166c915c25dc88337aa5f` |
| TFTP/boot console | 10255 | `182ccf7e6a962cdd7b4b5d0447f3195fe737c1159c88e5fbe5fa8ef3d9f9310c` |
| Complete descriptor/diagnostic capture | 9191 | `fc6063ca029e8b6b5f02e800aabb31b08f030ef2aaa4cacd81306a56abd24e00` |
| Shared-clock lifetime capture | 12364 | `4d542c444eb1dd9c0d9282eda9835f4210f36175d79cb5776acbd93f8f36a641` |

Raw logs remain ignored locally. The controller collector requires both real
bindings/root hubs, time64 and absence of clock failures. RDA presence is
recorded separately so a working host is not mislabeled as working Wi-Fi.
Actual DT/config mutations, bounded RAM plan, 29 serial PTY cases, shared-helper
2048 SDK trace comparisons, core lint/build/test and candidate QEMU passed
locally. Remote results for the new planner/collector remain pending.
