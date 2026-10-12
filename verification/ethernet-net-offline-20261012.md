# Inherited-PHY Ethernet RAM candidate: offline acceptance

Date: 2026-10-12. This records build/emulation checks; separate [physical
Ethernet acceptance](ethernet-net-20261012.md) identifies the booted image
and actual traffic. Hinas, CA fastboot, storage and OTP were not modified.

Profile: `6.12.112-ty1208z-ethernet-net1`, low 256 MiB of RAM, single core,
storage/USB/modules/SMP disabled. PHY identity derives from the preceding
[physical clock/ID measurement](ethernet-clock-id-20261012.md): FESTAv220,
`0x20669823`, address 1. The driver validates the actual ID again and preserves
PHY reset/firmware/expanded-register state. Ordinary negotiation may write
volatile PHY configuration. This is not complete cold-start PHY support.

## Candidate identity

| Item | Result |
|---|---|
| uImage bytes | 2900564 |
| uImage SHA-256 | `0f17565d666fd52833fbe84f5fc29cccec58744a73c876e660cf896bbc5d44c4` |
| uImage CRC32 | `66ead73b` |
| zImage SHA-256 | `3906a9c4a02ca8b4a17b6343765aa17860428950d59d2b249754cda8b0b6ee29` |
| Expanded Image SHA-256 | `ddaa9f3056393e671f41c10f0003138c82a6c1a463f408ea36f414325f88bc73` |
| Kernel physical start | `0x00008000` |
| Kernel physical BSS end | `0x006b7a20`, below reserved allocation lower bound 16 MiB |
| RAM header / load / entry | `0x01ffffc0` / `0x02000000` / `0x02000000` |

## Checks performed

This supersedes the initial offline candidate at `f60474c`. That revision's
persistent TX-ready NAPI loop was reproduced with actual patched functions.
The corrected RX/NAPI/ISR/monitor functions pass ASan/UBSan integration for
all lengths, TX-only level status, masked shared IRQ, pending RX preservation,
RX arrival between polls, normal/zero budgets and no-RX completion scheduling.

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

## Later tooling rebuild

The subsequent build enables fancy ping and usage output, and checks the
actual ARM applet for `-c CNT` and `-I IFACE`. It passed `make lint`,
`make test-serial`, the separate network build, compiled config/DT/image/layout
checks, actual driver-function sanitizers and QEMU time64. Its uImage is
2907852 bytes, SHA-256
`80b28a8589143cbedfbdc26deb3d777e1b514f3573f6c652fd11f8a5dceb2fbf`;
BusyBox SHA-256 is
`b337194b2814560f7ad485e57d490a60ea3c11c3460a2cb7cf25188ac9f3be4c`.
Its BSS end remains `0x006b7a20`. This later tooling image is hardware untested
and is distinct from the image in the identity table above.

## Remaining hardware acceptance

Dedicated PHY/MAC binding, DHCP, gateway replies, MTU pings and three software
interface cycles passed in the [physical report](ethernet-net-20261012.md).
Continue with cable removal/reconnection, sustained bidirectional transfers
and checksum behavior. Complete PHY
cold-start/reset/firmware initialization and physical OpenWrt/Passwall
performance are separate unfinished milestones. No installation or flashing
is authorized or implied by this candidate.
