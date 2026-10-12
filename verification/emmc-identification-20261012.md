# Restricted eMMC identification — hardware acceptance

Date: 2026-10-12. The installed CA bootloader and Hinas were preserved.
Only a RAM candidate was transferred and started; no flash, environment,
OTP/eFuse, card settings or storage-content writes were issued by this test.

## First candidate: initialization stalled

| Item | Observed result |
|---|---|
| Candidate bytes | 2251491 |
| uImage SHA-256 | `7d15ba1ac86484250d064ed499d7afe29650207f43acba4368ea692eca9d2426` |
| Host/device CRC32 | Both `7d6cbc33` |
| Boot | Installed CA fastboot accepted the ordinary uImage; Linux 6.12.112 started |
| Controller checks | Exact inherited resources/clock/register guards passed; PIO selected; DW version `270a` |
| Card/shell acceptance | Failed: no card identification or initramfs prompt observed; subsequent bounded console probe received zero bytes |

Local raw boot record: `ram-boot-20261012T100503.519360Z.rx`, SHA-256
`081b385202e83a13338afd74bb1a1904812f7a83fcb01adb9cba703b58aa9993`.
Follow-up probe: `board-diag-20261012T100932.366967Z.json`, console timeout.
Raw records remain in ignored local evidence; no unique card identity was published.

The final messages were `EMMC_IDENT_GUARD_PASS`, `Using PIO mode.` and
`Version ID is 270a`. In the fixed mainline source, IRQ registration and
interrupt enable follow that version message, before slot registration.
This localizes the next investigation; it does not prove the exact failing
instruction or an interrupt storm.

## Follow-up candidate: controller takeover

The restricted platform's initialization now logs inherited controller/IDMAC
interrupt state, disables inherited DMA/interrupt enables and clears known
W1C status bits before generic IRQ registration. The forced-PIO probe keeps
FIFO interrupts masked until `dw_mci_submit_data()` enables them for an actual
data transfer. Other platforms retain the original probe mask.

Card-command policy, PIO/1-bit/25-MHz limits, BLOCK exclusion and the fixed
resource/security boundaries are unchanged. The new register accesses only
change controller state; they do not add card settings or sector commands.

The actual platform initialization passes a host C harness with inherited
DMA/interrupt state and real fixed register definitions, including W1C status
semantics. Identity mismatches produce no writes. Request-policy/queue-entry
tests, standalone build, image/layout checks, profile gates, serial/RAM tools,
register-audit regression and QEMU RAM time64 pass locally.

Follow-up uImage: 2251243 bytes, SHA-256
`d44ab50252809a8dcefc612999a1c30c4da0fc288515636b615532186b184a01`.

This follow-up passed physical controller takeover and shell startup. Its
host/device CRC32 was `b617016c`. Inherited state was:

```text
CTRL=02000000 BMOD=00000202 IDINTEN=00000103 IDSTS=00000102 RINTSTS=00000000
PIO_QUIESCED CTRL=00000000 BMOD=00000202 IDINTEN=00000000 IDSTS=00000000
DW MMC controller at irq 18,32 bit host data width,256 deep fifo
```

The GIC reports eight MMC interrupts at hardware IRQ 67 without continuing
growth in the idle one-second diagnostic interval. UART, timer and the RAM
time64 probe work. Card enumeration stops because the request guard rejects
CMD1; no card device is published. The CLI correctly reports incomplete
identification, rather than treating the working shell as storage acceptance.

Local boot raw SHA-256:
`551db9816ea3b749ce9647ce5eae68206702fdff52624189877d6dd9f0c38b26`;
diagnostic raw SHA-256:
`29dea94275722ed350534a0aa70fa581f985c505cb1657d596419144bb7db36f`.

## CMD1 protocol correction

Linux 6.12.112's actual `__mmc_send_op_cond_cb()` repeats a busy OCR query
using `cmd->resp[0] | BIT(30)`. A dual-voltage eMMC OCR contains bit 7; the
original mask omitted it. The restricted policy now permits that standard
bit, while retaining the host's fixed 3.3-V signal and rejecting unsupported
OCR/reserved bits. No voltage-switch or storage-setting command was added.

The host regression now executes that actual core callback against the actual
policy, including a busy dual-voltage response and the ready transition, and
checks all 32 OCR bits. It passes with the request/sidecar and takeover tests.
The third candidate builds and passes the image/profile/QEMU gates locally:
2251267 bytes, SHA-256
`f53977474d5fc562cff1ed0e53162ad2da99d7a3602f3073ccecfd1f7ba33597`.
This exact third candidate passed physical identification and the guarded
CLI acceptance check. Host/device CRC32 both measured `7e055418`.

```text
EMMC_IDENT_CMD1 arg=00000000
EMMC_IDENT_CMD1 arg=40ff8080
EMMC_IDENT_CMD1 arg=40300000
mmc0: new MMC card at address 0001
type=MMC
name=008G30
manfid=0x000011
EMMC_IDENT_COMPLETE sectors=15269888 bytes=7818182656 ext_rev=8 clock=25000000 bus_width=0 timing=0
BLOCK_DISABLED
```

The observed retry argument confirms that bit 7 was required by this card.
`bus_width=0` is the MMC core's one-bit enum; `timing=0` is legacy timing.
The decoded name and capacity match the original Hinas baseline. All CMD6
attempts remained rejected, including erase-group definition, power-off
notification and HPI setup. The core consequently reported HPI/cache not enabled;
these messages are expected for this restricted identification profile.

MMC GIC hardware IRQ 67 remained at 14 during the one-second idle interval;
timer interrupts increased by 101, UART remained bidirectional and `Err=0`.
The RAM-file time64 test read back `2208988800`, with eight-byte `time_t`.
No host/board clock change was made. No unique card CID or serial is published.

Local evidence identities:

| Record | SHA-256 |
|---|---|
| `ram-boot-20261012T103425.013861Z.rx` | `72ca5d10b523f06550fa84090c60270ca9d28b1fccd2c4b2841958eda7393c70` |
| `board-diag-20261012T103846.527654Z.rx` | `e3a0131588add46f964bd4466334ca52210adb42fbbacfa0b7705cc21429bbc1` |

The CLI returned `diagnostic-captured`, `kernel_verified=true` and
`report_complete=true`. This accepts the restricted PIO metadata path only.
Sector reads, block-device integration, filesystems and Hinas startup under
the new kernel remain unproved; this is not an installation image.
