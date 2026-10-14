# Fresh-build CI repairs

2026-10-15. The installed system's physical acceptance is separate from these
fresh-source checks. Three failures on 40cd3f0 were traced to:

- The eMMC driver harness lacked stubs for the newly accepted persistent
  shutdown. It now checks the actual idle host retention/IRQ/clock writes and
  the active/missing-host refusals, preserving its read-only tests. ASan/UBSan
  passes locally against the current authoritative driver functions.
- Independent application variants did not explicitly deselect the new system
  Kconfig symbol, causing noninteractive syncconfig to prompt. The shared
  application fragment now explicitly disables this separate opt-in profile.
- The larger combined QEMU archive exceeded the initial rootfs tmpfs quota.
  Selecting ramfs fixes extraction, but copying a complete second root then
  exceeds 768 MiB. A 386217472-byte synthetic archive reproduces guest-global
  OOM killing cp with the original native /init copy operation. The gated
  QEMU-only entry now copies/unlinks each file into a tmpfs root before starting
  native /sbin/init/procd, limiting the extra copy to one file. Its tmpfs quota
  is 90% of the unchanged 768-MiB allocation. The same large fixture then reaches
  the native shell with a verified tmpfs root and no guest-global OOM.

The native source/archive and its /init remain unchanged; the QEMU fixture's
handoff now replaces execution of that /init. No disks or host networking are
added and no runtime success markers are removed. This repairs emulation
bootstrap only; it does not change installed firmware or establish a new board
memory claim. Earlier combined runtime evidence used the older native /init
handoff; the current full fresh-build run must pass independently.

Remote results are pending. The first 5bba089 combined rerun stopped at a
BusyBox HTTPS download timeout, before compilation/runtime; it was retried once.
