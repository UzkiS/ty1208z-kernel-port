# Onboard SD controller command-free physical audit

Date: 2026-10-13 UTC. This is a register observation, not SD card acceptance.
The exact Chinese native RAM router remained running throughout; no reboot,
persistent boot change, card command/data write or security-state write occurred.

## Exact module and router

Temporary ARM module: 108356 bytes, SHA-256
`43e45e9cf0572446c464f105396d2e99ebf444472ce93b4d894a2ebdb9412857`.
Authoritative SD driver source SHA-256:
`2c67112dddd1ae9a47ea6109c4bac46cfae7fba57dfac42f3da414c9af049415`.

Exact router zImage SHA-256:
`45461a65f4f6e04b313beb60dc086480ffd880508f8c4dbf214cdb0acf1f04e0`.
Kernel config SHA-256:
`25c1ec112d9a6b31ec7c5057152021b508c935ac6e1113d5249e9ae4dd11104c`.
The builder checked the real native kernel config/image/symbols, delivered DT,
GCC 14.3/musl identity and module ARM ELF/vermagic. BLOCK/MMC remain disabled.
The module's source/resource identity and SHA were checked again before load;
the transferred RAM file's SHA matched before `insmod`.

## Measured inherited state

| Register | Value | Interpretation |
|---|---|---|
| CRG39 | `00000203` | Bus/source enables set, reset clear; SDK source 50 MHz |
| LDO | `00000060` | Raw inherited value only; no regulator change |
| CLKDIV / CLKSRC / CLKENA | all zero | Card clock disabled |
| CTYPE | zero | Inherited controller setting; no card protocol negotiation |
| FIFOTH | `00ff0000` | Configuration observation only; FIFO never read |
| CDETECT / WRTPRT | both zero | Active-low card signal; true card presence still unconfirmed |
| USRID | `07967797` | Inherited controller identity |
| VERID | `5342270a` | DW revision low 16 bits `270a` |
| HCON | `00e44c81` | Controller configuration; no capability-driven writes |

The three resources were initially unclaimed. The exact probe bound, emitted
`SD_AUDIT_CONTROLLER_READ_COMPLETE` and
`SD_AUDIT_READ_ONLY_COMPLETE no-card-commands no-control-writes`.
No FIFO, interrupt/status, DMA, command, clock or regulator writes were made.
Actual card presence was not supplied by the user during this measurement.
The active-low signal is insufficient to establish a responsive SD card.

`rmmod` removed the module and device; all three MMIO reservations were released.
Router UART/timer/Ethernet IRQ Err remained zero and the accepted restart module
remained loaded. Chinese OpenWrt continued online.

Local evidence: `evidence/native-sd-audit-20261013T160305.392557Z.json` and `.rx`.
Received stream SHA-256:
`e8fd2b2f8888871e17c2b80041f9796ec58a85f739b7e1d0e628a1a602d40afe`.
Only anonymized measurements are tracked.

## Offline and emulation checks

`make lint`, `make build`, `make test` and `make sd-audit` passed locally.
Actual standalone/native probes passed resource/map failures, foreign board
denial, 128 clock/reset combinations and exact read order under ASan/UBSan.
Actual module init/exit passed failed driver/device registration, failed-probe
unwind and removal. Both exact restart and SD native modules compiled.
The standalone rebuilt SD image passed DT/config/CRC/RAM gates and QEMU shell/
time64; QEMU does not establish board-controller behavior.

SD card identification, sector reads, filesystem access and hotplug remain
pending. The standalone `sd-audit1` image itself remains hardware untested.
