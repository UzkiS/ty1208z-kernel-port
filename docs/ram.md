# Bounded higher-memory experiment

The measured board contains 1 GiB of DDR. Accepted ordinary diagnostics and
the current native router expose low 256 MiB with low 16 MiB reserved. The
original loader's eleven observed allocations begin at 0x3e507000; ddrfree
alone does not subtract them or establish the complete secure-memory map.

`make ram768` creates a separate single-core, low-768-MiB candidate. It keeps
low 16 MiB reserved, excludes the upper 256 MiB and enables no disk, network,
USB, module, highmem, PM or watchdog-device subsystem. Its dedicated reset
driver uses the independently measured MV100 identity/inactive-register gate,
with no startup writes and one explicit restart callback.
ARM normally returns its own freed init pages to the allocator, including
pages below the DT reservation boundary. This dedicated profile retains its
init area to keep every stress-test allocation above 16 MiB; generic and
ordinary router reclamation remain unchanged.

RAM planning requires the actual immediately preceding guarded reboot's
hash-verified allocation table in addition to the fresh attached inspection.
All eleven addresses/sizes and the CA/1-GiB identity must match; changed or
stale evidence denies the enlarged profile. Kernel/load/decompressor placement
remains independently checked below the existing limits. This experiment
does not authorize increasing ordinary router memory or persistent installation.

The explicit diagnostic creates a new file in a dedicated tmpfs under /tmp.
It verifies at least 700 MiB MemTotal and 560 MiB available before allocating
512 MiB. Two complete address-dependent/complement patterns are written and
read back. Pagemap must report every page present, unswapped and within the
profile's physical range, with at least 256 MiB of pages above 256 MiB.
The file and mount are removed before restart. Device files are never opened;
wall time is unchanged. QEMU tests generic shell/time64 and actual helper
mutations; its physical address map does not validate these board PFNs.

Physical acceptance now passes: 763068 KiB MemTotal (about 745.18 MiB), two
complete 512-MiB patterns and every mapped PFN within the boundary. 76207
pages (about 297.68 MiB) lie above 256 MiB. File/mount cleanup, command restart
and restoration of the exact Chinese router/configuration pass without user
power cycling; [physical report](../verification/ram768-board-20261014.md).
The ordinary restored router retains its original memory bound. The separate
native integration below now passes physically. Docker still requires its
own kernel, storage, daemon, container, resource and network acceptance.

## Independent native-router integration

The new make target openwrt-router768 builds the pinned official OpenWrt
applications and measured Ethernet in its own router768 source tree, with a
separate board identity, kernel configuration and artifact directory.
The ordinary application and router builds keep their original memory bounds.

The new configuration retains the low init pages only on that exact board.
Its Ethernet clock/MAC/PHY and external restart-module probes accept the
new identity only when the matching higher-memory configuration is selected.
It still excludes block storage, MMC, USB and SMP. This step integrates
memory and Ethernet; it does not yet provide SD/eMMC or Docker runtime.

The same fresh, complete loader-allocation table, low reservation, kernel
layout, exact kernel/rootfs provenance and independent kernel/initrd device
CRCs gate a physical boot. Both isolated application QEMU budgets remain
required. QEMU does not establish the physical board's PFN bounds; the
512-MiB probe and application checks were repeated on the native kernel.
Physical acceptance passed with 762296 KiB MemTotal (about 744.43 MiB),
all 131072 PFNs in bounds, 64-MiB TCP transfers in both directions, both
proxy cores and automatic configuration/Chinese-router restoration;
[native board report](../verification/openwrt-router768-board-20261014.md).
Clean CI for this new integration remains pending.
