# SD read-only block and VFAT physical acceptance

Date: 2026-10-13 UTC. The separate `sd-ro1` RAM image exposes the inserted
SDHC as a read-only block device, discovers two existing partitions, reads
sector data and an existing VFAT file, then automatically returns through the
original CA loader. No card data writes, filesystem repair, persistent boot
changes or security-state writes were performed. Native-router integration
remains separate.

## Exact accepted image

| Payload | Bytes | SHA-256 |
|---|---:|---|
| uImage-UNTESTED.bin | 3066886 | `ebb208f18cd9e0a31dd1f9797ea1e0f357ce8776aada3f38ef1dd00c42e0727f` |
| zImage | 3064744 | `f81db7d21aea5573bbd1922329fadd63526c02472f82d8cc73349f796bab34dc` |
| ty1208z-diagnostic.dtb | 2078 | `fc931122b61c2e617df5d04da51eda49ac4887883be96262cf0fdedd88754ce0` |
| linux.config | 47163 | `7debe2da6213a547fcdb0dbfb9f9a551457d56b04a6d1d28e9f04a6a49023d4c` |
| sd-ro-probe.armhf | 429292 | `8f3742c9e9fb7b0c7def4c97335f3352c77c71267898ed0773dd29877b4787d1` |

Fresh loader inspection, exact bounded RAM placement, immutable TFTP receipt
and independent device CRC32 `fe036e35` passed before boot.
Header/load/entry remain `0x01ffffc0` / `0x02000000`. Kernel physical BSS ends
at `0x007b1758`, below the reserved low 16 MiB; only low 256 MiB is exposed.
The kernel is `6.12.112-ty1208z-sd-ro1` with its dedicated board identity.

## Actual storage and filesystem results

The measured `SU04G` SDHC remains 3965190144 bytes (about 3.69 GiB), single
line, legacy and 25 MHz. Inherited controller/CRG39/LDO guards pass and PIO
is used. Linux registers `mmcblk0` as `(ro)` and discovers `p1 p2`.
BLKROGET returns 1; the complete 4096-byte first-page read passes, and a
1024-byte read crossing the page boundary matches its overlap with that page.

| Existing partition | MBR type | Start sector | Length sectors |
|---|---|---:|---:|
| p1 | `0c` | 2048 | 40960 |
| p2 | `83` | 45056 | 2056192 |

Partition type does not establish a filesystem. The first partition's VFAT
signature is recognized; a read-only mount reports fragment size 2048 and
10211 blocks. The bounded, symlink-free probe opens one existing regular file
with O_RDONLY and reads 360 bytes. No filename, contents or card serial is
printed. The mount is removed and the diagnostic records exactly one complete
filesystem mount/read/unmount. The second partition's filesystem is unknown
to this probe and was not mounted; its `83` type is not labeled ext4.
The card's capacity is not the sum of the two existing partition lengths.
No partition growth or formatting was attempted.

UART/timer/SD IRQ Err stays zero, and the RAM-file time64 probe passes with
8-byte time_t and epoch 2208988800. The board wall clock is unchanged.

## Enforced read-only boundary

The exact SD variant forces get_ro=1 before any GPIO/controller read. Its
request validator separately requires an identified sector-addressed SD card
with 512-byte sectors and checks capacity before hardware queueing. It allows
CMD17 and at most eight-sector CMD18 reads; multi-block requests require the
exact read-only CMD12 STOP sidecar. Standalone read-error recovery STOP is
also constrained. Writes, erase, CMD6 SET, CMD23, unknown requests, oversized
or out-of-range data, mutated flags and extra/malformed sidecars are denied.
Clearing a userspace disk read-only flag does not remove this queue barrier.
No physical write or clear-read-only test is performed.

The 4-KiB limit meets Linux 6.12's minimum block-queue page size rather than
advertising the metadata-only profile's unusable single-sector block limit.
PIO/single-line/legacy/25-MHz restrictions and the measured CRG/LDO gate remain.
Only this profile enables MMC_BLOCK, DOS/GPT and ext4/VFAT/exFAT. An ext4 mount
would additionally use ro,noload; actual ext4/exFAT mounts remain unverified.
No eMMC, network, USB, loop, RAM-disk, debugfs, module or SMP driver is enabled.

The initial image (3066382 bytes, SHA-256
`7a24c63e9b7941b1d8b3f3b8b3d85df16d76c8a50f5f477118c513f981d78abe`)
already passed block/page/overlap reads, but its shell loop could not parse
arithmetic disabled in minimal BusyBox. It did not reach filesystem mounts.
Replacing that counter with existing awk and checking the real ARM BusyBox
shell syntax produced the distinct final image above, which was transferred,
device-CRC checked and physically tested again. Earlier evidence is not
relabeled as filesystem acceptance.

## Shutdown and autonomous return

The UART restart tool verifies the dedicated DT, actual bound restart driver,
measured MV100 watchdog registration, read-only block state and absence of
card mounts. One restart is sent; actual DW removal/read-back emits
SD_IDENT_SHUTDOWN_COMPLETE host-removed clock-disabled no-card-writes.
The tool observes Boot ROM, DDR and original CA Fastboot, stops autoboot and
performs five fresh read-only loader queries. There is no reset retry.
The exact Chinese dual-core router is then transferred with two independent
device CRCs before RAM boot. The returned Chinese router restored all 14 selected
configuration/account/key hashes from the latest verified backup; root remains
empty. Actual host blank-root login reaches the Chinese Passwall page with HTTP
200, IRQ Err0 and the exact restart module is loaded/registered again. Final
restored-router stream SHA-256:
`0449e1c6918d33bbf9c8dc2031a19c28485cae218db81ddfd77fab0faefaf450`.

Boot: `evidence/ram-sd-ro-tftp-20261013T173116.091757Z.json` / `.rx`, received-stream SHA-256
`605bf685fd675333c26665062c4633b0011715a47dfd94313129bcde3351ecc5`.

Diagnostic: `evidence/board-sd-ro-20261013T173116.091757Z.json` / `.rx`, received-stream SHA-256
`22b3e3d89e9ad3aa05c225ec0b3d144a2869572f9f89d9547268ff2b20d4c977`.

Restart: `evidence/sd-ro-restart-20261013T173635.095366Z.json` / `.rx`, received-stream SHA-256
`230f2637829f9336cd61cc7e18bf76f9007ee41bcea0e1a967ad06af948156c5`.

Raw local logs stay ignored. The tracked report contains only non-unique,
anonymized observations.

## Local validation and remaining integration

Core make lint/build/test, updated serial PTY, both SD builds, ARM image/CRC/
layout and QEMU shell/time64 checks pass. Actual driver/policy/DW queue and
forced-ro callback pass ASan/UBSan, including all commands/directions, end-of-
card, flags/STOP mutations, absent/non-SD cards and GPIO/WRTPRT overrides.
Probe/slot/shutdown/takeover/restart checks pass in both SD configurations.
Compiled DT/config/resource mutations and the bounded RAM planner pass.
QEMU does not emulate the physical SD controller or establish filesystem
mounts on this card. Original metadata-only byte identities remain separate.

Physical hotplug, ext4/exFAT filesystems, SD production-router integration,
write support and performance remain pending. eMMC block/backups, higher
usable RAM, actual Docker containers and RDA STA/AP remain required work.
This RAM result is not persistent installation acceptance.
