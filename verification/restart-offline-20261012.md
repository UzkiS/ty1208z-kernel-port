# SP805 explicit restart candidate: offline acceptance

Date: 2026-10-12. The candidate has not been booted physically and no new
restart command has been sent to the box. Build and emulation do not prove
that the MV100 resets or that its real watchdog ID/control match the gate.

| Item | Actual build result |
|---|---|
| Kernel | `6.12.112-ty1208z-restart1` |
| uImage bytes | 2201344 |
| uImage SHA-256 | `e1a45c2e5575c737ff72adad9834f2194678288b2e2358a28a8a657665ceb5b9` |
| uImage CRC32 | `d5f72a9b` |
| Raw zImage SHA-256 | `78dd6c68e9657593c264ca7c11629c252f9761affa199cb6f8e9a14aa275c6fa` |
| Expanded Image SHA-256 | `299090dcd2600a28288ba958683e7e4991900b667c2b55305d68897fcbf76aa3` |
| Decompression footprint | `0x00008000..0x005adde8`, below 16 MiB |

The actual source helper passed ASan/UBSan. Tests cover ordered ID/control
reads without writes, every relevant peripheral/cell identity bit and every
CONTROL bit mutated, active watchdog states, all permitted high-byte
revisions, exact four reset writes and the posted-write flush. These execute
the helper compiled into the candidate; they do not emulate the reset signal.

The compiled DT/config gate passed. Mutations reject changed addresses/size,
ID overrides, broader subsystems, foreign identity and extra watchdog/reset
nodes. The initially rejected automatic POWER_RESET_HISI selection is now
explicitly accounted for: its driver cannot bind in the exact DT. Additional
reset drivers and any of its matching DT nodes remain rejected.

The common base diagnostic was rebuilt and passed core configuration,
image/layout, generic ARM/QEMU time64 and RAM-boot protocol regression. The
dedicated restart image then passed uImage CRC, appended DT, static ARM ELF,
actual decompression footprint and the same raw kernel/initramfs QEMU
time64 round trip at 2040. QEMU does not emulate this board's watchdog.

Latest lint and serial PTY integration passed. The board-report tool requires
actual observed IDs/disabled control and handler registration. The separate
restart tool refuses bootloader/Hinas/missing registration or echoed completion,
does not retry a failed reset, and verifies a fresh identified CA boot through
completion of the fixed read-only queries. No physical execution occurred.

The guarded RAM plan passed against the recorded inspection and exact image
hash/layout. The pending native Ethernet image was independently rechecked;
its original identity and valid placement remain intact. Live loader and
device CRC checks are still required before either image is booted.

Source/resource rationale and the exclusive UART workflow are in
[restart support](../docs/restart.md). CI is extended with this independent
build/check step; an actual result must be inspected before claiming CI
acceptance. The next hardware evidence must show real IDs, no startup writes,
one explicit reboot and a fresh CA bootloader with unchanged persistent path.
