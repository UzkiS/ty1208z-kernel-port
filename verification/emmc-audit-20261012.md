# Physical eMMC register audit, 2026-10-12

The separate RAM image booted through the existing CA fastboot and completed
the fixed register audit with a usable Linux 6.12 serial shell. MMC and BLOCK
were disabled. This establishes controller identity and inherited clock state,
not card enumeration or storage access.

## Exact local image and evidence

| Item | Identity |
|---|---|
| Kernel release | `6.12.112-ty1208z-emmc-audit1` |
| uImage size | 2226820 bytes |
| uImage SHA-256 | `7dc0ad1412ac0f80110799129496301dc7d54d4585f55495c0853ab8a2755f62` |
| Device/host CRC32 | `cd246307` |
| Transfer/boot RX bytes | 10231 |
| Transfer/boot RX SHA-256 | `a09167434fd9aa8658c9ea45078bb8a011c6476fd48366b5dd0a182446295c89` |
| Complete diagnostic RX bytes | 7606 |
| Complete diagnostic RX SHA-256 | `40bfb0ab5e054097a628ae8b980875d72919521ee5e32ba353aaf6096518beb8` |

Raw logs remain in ignored local evidence. No serial number, MAC address,
credential or firmware content is included here.

## Measurements

| Register | Value |
|---|---|
| CLKDIV | `0x00000001` |
| CLKSRC | `0x00000000` |
| CLKENA | `0x00000001` |
| CTYPE | `0x00010000` |
| FIFOTH | `0x207f0080` |
| USRID | `0x07967797` |
| VERID | `0x5342270a` |
| HCON | `0x00e44c81` |
| CRG40 | `0x00040103` |

The driver printed `EMMC_AUDIT_READ_ONLY_COMPLETE`. The pinned SDK clock field
decodes to 100000000 Hz. VERID's low 16 bits identify DW revision `0x270a`;
HCON reports a 32-bit FIFO interface and internal 32-bit DMA. The audit does
not test DMA. Inherited CLKDIV=1 implies a 50 MHz card clock; CTYPE indicates
8-bit operation. FIFO thresholds match the SDK's 256-entry configuration,
but thresholds alone do not independently measure FIFO depth.

CPU0 timer interrupts increased 1641→1743 and UART interrupts 103→343 during
the one-second check; Err=0 and uptime increased 16.40→17.41. MemTotal was
244480 KiB. The RAM time64 probe passed: 8-byte time_t, file timestamp
2208988800 (2040-01-01), monotonic interval 50066375 ns. Wall time was not changed.

## Validation and limits

Local build, configuration/resource gates, ARM image/CRC/decompression checks
and QEMU RAM userspace/time64 passed before this hardware boot. CI also passed
for `da5031d` ([run 38212036870](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38212036870))
and the boot-marker fix `3df7efc`
([run 38212760978](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38212760978)).
CI reproduces source/build checks; its binary is not claimed to have the exact
identity of this physically tested local image.

The audit performed whitelist MMIO reads only: no FIFO/status reads, controller
writes, clock/reset changes or card commands. No persistent boot changes,
flashing, filesystem mounts or OTP/eFuse writes were issued by the project.
The next stage must separately test restricted card identification. It must
not infer safe write access from these measurements.
