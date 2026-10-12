# Guarded CA bootloader inspection — 2026-10-12

The complete original boot was already captured. The missing evidence is a
live command/help and environment response at `fastboot# `, not another Linux
boot log. This inspection sent no load or boot command; subsequent RAM transfer
and candidate boots are recorded separately in [the RAM boot report](ram-boot-20261012.md).

## Physical attempts

Both attempts identified a fresh original CA boot, wrote one Ctrl+C byte and
stopped when the original kernel started. Neither received a bootloader prompt;
**zero query commands were sent**. No retry, environment change, storage or
security command was issued.

| Attempt | Trigger | Received bytes | Outcome |
|---|---|---:|---|
| 03:48 UTC | Printed autoboot prompt; 200 ms serial read timeout | 9940 | Original Hinas continued booting |
| 03:55 UTC | Earlier reservation table; 10 ms read timeout, TX before log flushes | 10208 | Original Hinas continued booting |

Local raw SHA-256:

- First: `b779eb128f8ac94c87564265612c821e9145fc2a27c5bec37546dc466fbf54f4`.
- Second: `41c2e43b9a27bee81352b549b8f5d8a4d74c6348692affd2e22e22a635a13fa9`.

An isolated CR test subsequently received only `0d`; a CRLF test received only
`0d0a`, without a new login prompt. The latter raw SHA-256 is
`7eb70257593da06f682a3ddda54a9d260d4fc514f645237f5ca74b08f8da61a6`.
These bytes do not establish successful board-console input. The user reports
that Enter in HiTool can produce a login prompt. HiTool's saved terminal
settings match the CLI: COM5, 115200, 8N1, no flow control. The discrepancy
remains unresolved; neither a wiring fault nor a software fault is established.
All operations released the port. Further reboot attempts are deferred while
console input and echo are investigated.

The CLI was listening before each reboot. Replying immediately after entering
`reboot` was correct; user message timing did not control the interrupt.

## Successful stopped-console inspection

After replacing the USB–TTL adapter, the user reached `fastboot# ` on COM9
(Prolific USB ID `067b:2303`). The host CLI then attached to the existing empty
prompt, checked the measured Fastboot version and completed fixed queries. No
Ctrl+C, reboot, load or boot command was sent during this inspection.

- Latest raw capture: 2491 bytes; SHA-256
  `9669c93e444d69dc4b332653fc9c93e45584a2ab2a3166c915c25dc88337aa5f`.
- Live `bootdelay=0` confirmed.
- `bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0` confirmed.
- `loadaddr`, `bootm_low`, `bootm_size`, `ethact`, `ethprime` and `autostart`
  are undefined. No variables were changed by this inspection.
- `bootm [addr [arg ...]]`; partial start/loados/cmdline/bdt/prep/go commands.
- `loady [ off ] [ baud ]`: YMODEM binary receive at a specified address.
- `loadb [ off ] [ baud ]`: Kermit binary receive.
- `tftp [loadAddress] [bootfilename] <upload_size>` is present.
- `crc32 address count [addr]`: omitting the third argument prints a checksum.
- `getinfo ddrfree` reports base `0x01000000`, size `0x3f000000`.

The SDK reference command computes ddrfree from DDR size and a fixed lower
bound, so high dynamic reservations must still be excluded. The measured
console responses establish command availability, not candidate boot success.
The historical failed attempts above remain recorded; their console blocker
is resolved by the adapter replacement.

## Offline evidence

The known-successful CA fastboot is hash-checked before extraction:

- Source SHA-256: `f891870ec98b4df48de879afc1e1973cf14cc9057eb18a5a41d974fab3e935bc`.
- LZMA-alone stream offset: 31128; extracted size: 750468 bytes.
- Payload SHA-256: `a1181bf31bef0ac8a0da40b6a1ecdaf142304e041255f559735361c1e0567b83`.
- Strings include `help`, `printenv`, `bootm`, `tftp`, `loadb` and `fastboot# `.
- ARM disassembly of the payload's main loop shows keyed autoboot and a default
  stop key of `03`, consistent with the original Ctrl+C prompt.

The local `bootargs9-32.bin` has SHA-256
`d6d2be7bd083b2e74a2d123fb968827539373600c01bdae193eea7656c015cd0`
and contains `bootdelay=0`. This is a local image measurement, **not a live
`printenv` result**. It suggests a very short stop window; the installed value
was later confirmed by live printenv. Offline strings and disassembly do not prove the
current transfer commands, DTB handoff or safe RAM placement by themselves.

## Fresh-boot interrupt after adapter replacement

At 05:44 UTC, the same CLI identified a new CA boot, sent one guarded Ctrl+C
and completed all five fresh-boot query commands. The adapter replacement
resolved the earlier physical interrupt failure even with bootdelay=0.
Raw capture: 7545 bytes, SHA-256
`0fe40d34ea95c98bdd232ab62327e253afa0fc97d9b98069155a8557f6fae94e`.
The console remained at fastboot after the port was released.

## Protocol validation

Linux pseudo-terminal integration covers capture and guarded inspection:
fresh boot identity, fragmented prompts, fixed query sequencing and TX journal,
wrong board rejection, stale prompt rejection, expiry at Linux login, missed
interrupt, late autoboot observation, and unexpected restart before or after
the interrupt. The original receive-only capture checks remain in place.
Local `make lint test-serial` passed; all 16 console PTY cases and five YMODEM
cases passed on Linux/WSL. Attach tests cover prompt/version gating, Linux login
rejection and a different Fastboot version. YMODEM tests cover CRC16, exact file
length/padding, sequence wrap, receiver-requested retries, both EOT handshakes,
cancel and startup timeout.

PTY success validates the host tool only. Physical read-only inspection is now
successful; RAM transfer and candidate boot are separate stages. A written TX
journal entry alone means the host serial driver accepted bytes, not that the
board received or acted on them.
