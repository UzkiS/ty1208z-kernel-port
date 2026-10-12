# Inherited-PHY Ethernet RAM candidate: offline acceptance

Date: 2026-10-12. This is build/emulation acceptance, not board Ethernet
acceptance. Hinas, CA fastboot, storage and OTP were not modified.

Profile: `6.12.112-ty1208z-ethernet-net1`, low 256 MiB of RAM, single core,
storage/USB/modules/SMP disabled. PHY identity derives from the preceding
[physical clock/ID measurement](ethernet-clock-id-20261012.md): FESTAv220,
`0x20669823`, address 1. The driver validates the actual ID again and preserves
PHY reset/firmware/expanded-register state. Ordinary negotiation may write
volatile PHY configuration. This is not complete cold-start PHY support.

## Candidate identity

| Item | Result |
|---|---|
| uImage bytes | 2900460 |
| uImage SHA-256 | `7fdd547d4db8c7f1235276ccf5f094108943fb9e869cc65dfc29689de23b2998` |
| uImage CRC32 | `390d5f61` |
| zImage SHA-256 | `d6d3b6ee96f113d1aeb84086ab48f120072f7da413abef257107d572ff0599c0` |
| Expanded Image SHA-256 | `a0d6d73ec7fea412fc810f1a07cd7cc731e9516adf89b9e5a256ba705813df13` |
| Kernel physical start | `0x00008000` |
| Kernel physical BSS end | `0x006b7a20`, below reserved allocation lower bound 16 MiB |
| RAM header / load / entry | `0x01ffffc0` / `0x02000000` / `0x02000000` |

## Checks performed

- `make lint`, `make build`, `make test` and `make test-serial` passed locally.
- `make ethernet-net` independently compiled the kernel/DT and a static ARM
  BusyBox with IP/DHCP/ping tools; required/disabled Kconfig and compiled DT
  were validated. Image CRC/header/appended-DTB and decompression placement
  passed; the RAM plan derives from the previously measured bootloader log.
- Actual clock/MAC setup/reset/length helpers passed ASan/UBSan: 160 control
  bit mutations, exact inherited values, clock enable/restoration faults,
  no-write behavior for changed ownership, exact MAC register setup, untouched
  `0x340`, reset pulses and all 4096 descriptor lengths before FCS subtraction.
- Profile mutation tests reject changed resources/clock/PHY, additional
  peripherals, reset/GPIO properties and unreviewed subsystems. NET is allowed
  only for the independently validated network profile.
- Serial Linux PTY regressions passed: exact kernel/PHY binding markers,
  bootloader/Hinas refusal and command echo cannot fake DHCP/ping completion.
- The same raw zImage/rootfs passed QEMU ARM shell and 2040 wall-clock/RAM-file
  time64, with no board hardware or guest NIC attached. This does not test the
  MV100 MAC, PHY, IRQ or DMA.

## Hardware acceptance still required

Bind the dedicated PHY and upstream MAC, then use the fixed temporary DHCP
and gateway-ping command. Record link negotiation, SPI 71 progress, ARP and
RX/TX/errors. Continue with repeated down/up, link removal/reconnection,
sustained bidirectional transfers and checksum behavior. Complete PHY
cold-start/reset/firmware initialization and physical OpenWrt/Passwall
performance are separate unfinished milestones. No installation or flashing
is authorized or implied by this candidate.
