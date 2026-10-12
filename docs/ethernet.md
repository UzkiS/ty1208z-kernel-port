# Hi3798MV100 Ethernet source audit

The existing Hinas uses `hieth` at `0xf9840000` and has demonstrated a
100-Mbit/s full-duplex link. The runtime FDT identifies internal PHY address
**1**, MII, GIC SPI 71 and a 0x4000-byte MAC resource. The reference SDK DTS
uses PHY address 2; the runtime measurement takes precedence. A working
Ethernet driver under Linux 6.12 has not yet been demonstrated.

## Reuse boundary

The pinned SDK's `drivers/net/ethernet/hieth/{hieth.h,mdio.h}` register layout
matches substantial portions of Linux 6.12.112's
`drivers/net/ethernet/hisilicon/hisi_femac.c` and
`drivers/net/mdio/mdio-hisi-femac.c`:

| Function | MV100 address/offset | Mainline representation |
|---|---|---|
| Port 0 | `0xf9840000` | First MAC resource |
| Port mode/link/frame limit | `+0x200/+0x208/+0x210` | Same register fields |
| Queue configuration/status | `+0x344/+0x36c` | Same depth and ready fields |
| RX descriptor/address | `+0x354/+0x358` | Same FIFO interface |
| TX address/length | `+0x360/+0x364` | Same FIFO interface |
| Global control | `+0x1300` | Second MAC resource, relative offsets |
| Forward/filter control | `+0x1310/+0x1314` | Same port-0 control fields |
| IRQ status/enable/raw | `+0x1330/+0x1334/+0x1338` | Same port-0 interrupt fields |
| MDIO control/read data | `+0x1100/+0x1104` | Separate MDIO resource |

The MDIO ready flag is bit 15, write flag bit 13, PHY address bits 12:8,
register bits 4:0 and write data bits 31:16. Mainline uses bounded polling
before and after each operation. A read command writes the MDIO controller
command register; it does not write a PHY register.

Matching offsets justify reuse of the upstream datapath and MDIO protocol,
but do not establish complete compatibility. Mainline also configures RX
coalescing at +0x340; the pinned SDK driver does not define that register.
SDK port initialization explicitly sets endian, TX preamble/IPG, pause and
RX checksum controls. These behaviors require comparison before hardware use.
The second MAC port must remain disabled until its wiring is established.

## Clock, reset and internal PHY

The SDK DTS supplies `PERI_CRG51_SF` to hieth, and the MV100 clock table uses
offset 0xcc with mask/value 0x000b and reset bit 4. Its name and apparent reuse
by another peripheral are insufficient to establish Ethernet clock ownership
or frequency. Live register state and a complete clock-reference audit are
needed before a new clock provider writes this field.

The pinned SDK `phy.c` and `mach-hi3798mx/include/mach/platform.h` describe:

- CRG internal PHY control at `0xf8a22120`: clock enable bit 0, reset bit 4.
- Peripheral control at `0xf8a20008`: internal/external PHY selection bit 8.
- Internal PHY address at `0xf8a20118`, low 5 bits.
- Internal PHY LDO control at `0xf8a20844`; the MV100 fallback writes 0x68.
- Reset order that gates the MAC clock before loading the PHY address, and
  waits at least 15 ms after PHY reset before MDIO access.

These are source facts, not newly measured board state. The first network
candidate should inspect the inherited control state and identify the PHY
before enabling MAC DMA, changing LDO/clock/reset or applying PHY fixups.
Reading PHY IDs via MDIO requires a bounded, explicitly read-only PHY command
path; attaching the generic PHY state machine can cause resets/writes and
must not be described as a register-only audit.

## Independent inherited-state diagnostic

`make ethernet-audit` now builds a separate `ethernet-audit1` RAM candidate.
It keeps NET/MMC/BLOCK/MTD/USB/MODULES/SMP/debugfs disabled and reuses the plain
diagnostic UART/timer/userspace. The driver validates six exact resources
before mapping them. It first reads CRG51, internal PHY CRG, selection, address
and LDO; none is written.

MAC/MDIO access is conditional on the inherited SDK fields: CRG51 mask 0x1b
equals 0x0b, PHY CRG mask 0x11 equals 1, selection bit 8 clear and PHY address
low five bits equal the measured address 1. Otherwise it reports a skip and
finishes without touching the MAC. This is an observation gate, not proof
of clock frequency or complete SoC initialization.

When the gate passes, only fixed MAC mode/queue/reset/forward/IRQ/control
registers are observed; no MAC address or FIFO/descriptor is read. Exactly
PHY 1 Clause 22 ID registers 2 and 3 are then read. Each operation polls MDIO
ready before and after its command with a 1-ms bound. The two possible command
values are 0x102 and 0x103. These write the MDIO command controller to request
a PHY read, with the PHY-write bit and hardware-ready bit clear; there are
no PHY register, clock/reset, IRQ-enable, packet/DMA or storage writes.

The real helper is executed under ASan/UBSan with an MMIO seam covering ready
and busy states, both completion timeouts, data masking and absent/all-ones
IDs. Profile tests reject changed resources and unreviewed subsystems. The
standalone build, serial identity gates, image layout and QEMU are checked
separately. A completed audit may report unavailable PHY ID; that must not be
described as Ethernet working. The [physical audit](../verification/ethernet-audit-20261012.md)
measured CRG51 `0x3` and skipped MAC/MDIO access because bit 3 was absent.
The internal PHY clock/reset, selection and address fields met the remaining
conditions; LDO was `0x8`. No PHY ID has been measured.

The vendor driver selects different volatile expanded-register fixup tables
by actual PHY ID. The [clock/ID experiment](../verification/ethernet-clock-id-20261012.md)
measured `0x20669823`, matching FESTAv220. The
SDK's OTP-derived trim routine explicitly excludes MV100 and must not be
copied from MV200/MV300 support. No OTP/eFuse writes belong in this port.

## Integration and acceptance

`make ethernet-clock-id` builds a distinct `ethernet-clock-id1` RAM experiment,
with a different compatible, release and an eight-byte MDIO resource. It
requires the exact measured controls: CRG51 `0x3`, PHY CRG `0x101`, select
`0x0e000004`, address `0x03000001`, LDO `0x8`. Only CRG51 bit 3 is enabled;
the complete readback must be `0xb`. After the SDK's 5-ms MDCK settling delay,
the same bounded PHY 1 ID helper runs and CRG51 is restored to `0x3` on success,
MDIO timeout or absent ID. Restoration is verified. Unexpected changed
control state stops the experiment without overwriting that state and without
claiming completion. NET/storage/USB/debugfs remain disabled.

This experiment makes volatile clock writes and MDIO read-command writes;
it is not the inherited-state read-only audit. It never changes the PHY clock,
reset, address, selection or LDO and never starts MAC DMA. The SDK clock table
sets mask/value `0xb` at `PERI_CRG51_SF` (`0xcc`), and the SDK DTS assigns this
clock to hieth. The common vendor prepare/enable path also toggles reset,
so it is deliberately not called by this limited experiment. Clock rate and
a complete cold-start sequence remain unresolved. Exact-state guards,
bit-only writes, busy/invalid-ID errors and restoration/readback failures are
executed under ASan/UBSan; DT/profile, serial identity, build and QEMU gates
are separate. A successful PHY read still does not establish network traffic.
The physical experiment passed with the exact clock restoration sequence
and FESTAv220 ID. No reset, fixup, link or MAC data transfer ran.

Keep network experiments separate from the storage and plain diagnostic
profiles. Use an MV100 compatible and an explicit upstream adaptation where
needed; do not masquerade as a hi3516 board to skip SoC integration work.
The production path should retain upstream DMA mapping, NAPI, PHY state and
error handling, with a 32-bit DMA mask and the measured RAM reservations.

Hardware acceptance must include PHY ID, IRQ progress, link negotiation,
ARP/ping, DHCP, TX/RX counters, checksum behavior and sustained bidirectional
traffic before routing/Passwall throughput testing. Tests must also cover
link loss/reconnection and cold boot without depending on Hinas to initialize
the PHY first. MAC addresses and identifying logs remain local.

Source identities are pinned in `config/sources.lock.json` and
`reference/reference-manifest.json`. This document records source analysis
and inherited-state measurements; a working Ethernet driver/image has not
yet been demonstrated.
