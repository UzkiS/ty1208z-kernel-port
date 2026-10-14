# 串口传输中断与接收排查（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The board still ran the previously accepted RAM-only
`6.12.112-ty1208z-ethernet-net1` image. A fresh fixed diagnostic returned
23385.06 seconds of uptime, UART/timer/time64 acceptance and the existing
Ethernet binding. No fresh boot was received by the armed bootloader listener.

## Attempt and observed failure

To obtain sustained TCP measurements without replacing the running image,
the pinned iperf 3.20 archive was verified against SHA-256
`3acc572d1ecca4e0b20359c7bf0132ddc80d982efeee20c86f6726a9a6094388`.
An independent static ARM EABI executable was built using the existing native
OpenWrt GCC/musl toolchain. ELF checks showed no dynamic interpreter and
QEMU user execution printed the actual 3.20 version. Its length was 206992
bytes and SHA-256
`83d4f5529d268b4b70ee2372ca99409ff8b9ab7290f1a6f13bf538134d485282`.

After verifying the exact running kernel, short fixed shell commands appended
80-byte octal-encoded chunks to a RAM file under `/tmp`. Every command was
under 480 bytes and waited for the diagnostic prompt. The intended subsequent
SHA check was mandatory before chmod or execution.

The exchange timed out during an append command. The final raw response
contains an incomplete echo and no returned prompt. The hash-check and
execution stages were never reached; iperf was not started on hardware and
there is no sustained TCP result. No storage or persistent boot operation was
sent. The experimental runner and partial RAM file do not constitute a
supported file-transfer method.

## Follow-up observations

A separate newline shell probe received no bytes. A bounded Ctrl+C/newline
attempt, then host serial reconfiguration and a second attempt, also received
zero bytes. Windows reported the connected serial device as OK. The board
continued to answer two IPv4 pings after these attempts, at 5 and 12 ms with
zero loss. This rules out a complete network-visible halt at that observation,
but does not identify a UART adapter, wiring, driver or userspace cause.

The guarded COM9 bootloader listener was restored. Native OpenWrt boot,
physical USB audit and sustained traffic acceptance still require a fresh
startup and working bidirectional console. Short-command acceptance from the
earlier physical reports remains valid within its recorded scope.

After the user reported completing the requested computer-side TTL USB
replug, the host still identified the same COM9 adapter. The previous empty
listener was stopped and the port reopened. A bounded Ctrl+C/newline probe
again received zero bytes; two host pings still received replies. The new
empty capture is `console-recover-20261012T212132.896506Z.rx`. This does not
identify the cause or establish console recovery. A fresh guarded listener
was armed before requesting a board power cycle; native OpenWrt transfer
must wait for an identified bootloader and successful bidirectional queries.

The pinned kernel's default serial termios includes `IXON`, and the diagnostic
init script does not disable it. A further bounded host XON (Ctrl+Q), then
empty-line attempt checked whether output might merely be flow-stopped.
Capture `console-xon-20261012T214836.902368Z.rx` was also empty. Two subsequent
host pings still received replies at 2 and 4 ms, with zero loss. Host control
character submission is not proof that the board received it; the cause
remains unestablished. The guarded listener was restored without boot, reset
or storage commands. No fresh board startup has yet been observed.

After the next user completion reply, that same live COM9 listener still had
zero received bytes. Windows reported the adapter OK, and two further pings
received replies at 4 and 15 ms. This is not evidence of a captured power
cycle or recovered UART. A question about the actual box power/LED transition
was left pending; the listener was kept armed rather than repeatedly reopening
the port or sending boot commands.

## Local evidence identities

Raw logs and experimental runners remain in ignored local storage.

| Record | SHA-256 |
|---|---|
| Upload RX `20261012T202712.306339Z`, 1038725 bytes | `bf4f55fe6f760010b342db92ab0dfa1d34623fe3021156907ecf709113a14ce1` |
| Upload TX journal, 2369 written commands | `e483ef9d81b3334563376d78a18cb067d9c2eb18170129c66b8e8583c0b4a29f` |

Both recovery captures were empty. Host ping results were observed in the
terminal, not saved as a standalone raw capture. Addresses, MACs and personal
paths are omitted here.
