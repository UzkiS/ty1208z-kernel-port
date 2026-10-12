# Fixed eMMC read samples — RAM diagnostic

Date: 2026-10-12. No flashing, persistent environment changes, mounting,
card-setting writes, data writes, erase, OTP/eFuse or security-state writes.

This independent profile enables exactly four single-block CMD17 requests in
the eMMC user area, with no block interface. It inherits the physically accepted
PIO/one-bit/25-MHz metadata path. Details and fixed LBAs are in [eMMC scope](../docs/emmc.md).

## Exact candidate and local checks

| Item | Value |
|---|---|
| Kernel | `6.12.112-ty1208z-emmc-read1` |
| uImage bytes | 2252555 |
| uImage SHA-256 | `5c0e26622a7e3ccba062e3a7494add72a5a4e394b34c6e5344858143e5153ab6` |
| Expected transfer CRC32 | `8cc947b6` |
| Physical BSS end | `0x005adde8` |
| Expected Hinas first-sector CRC32 | `2ba1a125` |

The checksum reference comes from the first 512 bytes of the local Hinas image
whose full SHA-256 is
`baaa86b45dc9f10ac9611695c1f37311ac6eda6315fd03e5fb2c8cf7f92afaf5`.
The regression uses a synthetic header with the same CRC, not firmware bytes.

Local checks passed: repository lint, standalone build/test, serial/RAM gates,
identification rebuild, actual restricted request/core callback and fixed probe
with ASan/UBSan, DT/config/profile/image/decompression gates and QEMU time64.
The tests inject command errors, data errors, short reads and R1 errors at each
of the four transfers; wrong identity/partition/bus state issues no reads.

## Physical result

Passed on the physical board. The installed CA fastboot accepted the ordinary
RAM image and the host/device transfer CRC32 matched `8cc947b6`.

```text
EMMC_SAMPLE_SECTOR lba=28672 crc32=2ba1a125
EMMC_SAMPLE_SECTOR lba=28673 crc32=686b40b7
EMMC_SAMPLE_HINAS_HEADER_MATCH crc32=2ba1a125
EMMC_SAMPLE_SECTOR lba=1249282 crc32=20c97f2a
EMMC_SAMPLE_SECTOR lba=1249283 crc32=ba528bdd
EMMC_SAMPLE_EXT4 magic=ef53 block_size=4096
EMMC_SAMPLE_READ_COMPLETE count=4 no-block-device
BLOCK_DISABLED
```

The guarded CLI returned `diagnostic-captured`, with kernel identity and the
complete report verified. MMC IRQ 67 remained at 24 during the one-second
idle interval; timer increased by 101 and `Err=0`. RAM-file time64 still passed.

This confirms PIO CMD17 transfer and the measured Hinas header/root partition
offsets for these samples. It does not establish filesystem reads/mounts,
full partition integrity, high-speed/DMA/multi-block I/O, Hinas startup or
storage writes. The box remains in this RAM diagnostic, with no network or
working soft-restart handler; the original Hinas is unchanged on eMMC.

Local evidence identities:

| Record | SHA-256 |
|---|---|
| `ram-boot-20261012T110042.830484Z.rx` | `b52158e953f7420d8cf472f2c3d67b478ce5b60b8b98a48d9d7f78c222df3785` |
| `board-diag-20261012T110539.235835Z.rx` | `0b3f69dfb088c0ba0ce08ecc16f1c63733b85dd333fab77c1dd61626c3f76cc5` |
