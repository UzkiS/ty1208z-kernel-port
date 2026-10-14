# 临时 TFTP RAM 传输离线验证（2026-10-13）

> 历史阶段记录：以下结论仅适用于所列日期、profile 和镜像；文中的“未完成”描述当时边界。当前能力与使用方法见 [STATUS](../STATUS.md)，阶段导航见[验证索引](README.md)。

The measured CA bootloader advertises
`tftp [loadAddress] [bootfilename] <upload_size>`. The optional CLI uses the
download form without an upload-size argument, at the same validated kernel
and external-initrd RAM addresses as YMODEM. Actual TY1208Z TFTP transfer,
throughput and boot remain untested.

## Implemented boundaries

The CLI freezes exact planned bytes before opening the console, checks live
Fastboot/version/DDR/bootcmd and the current TFTP/setenv help, then serves
only one or two exact immutable aliases to one IPv4 peer. UDP/69 is bound to
the specified local interface address. No filesystem directory or upload is
exposed. The server has a total deadline, bounded retries/request rejection,
octet-only transfers, bounded option negotiation and no block-number rollover.

Only volatile network variables are set. Automatic download boot is disabled
before the addresses change. Each download needs a completed server receipt
matching the planned bytes/SHA, the bootloader filesize and its RAM CRC.
The original address/mask/autostart values are restored and read back before
the service closes and boot may be sent. No saveenv, bootargs, bootcmd or
storage-write operation is introduced.

Loss of the known prompt prohibits restoration commands and boot; the report
retains a volatile-settings recovery status. A fresh startup is required in
that case. This implementation does not resolve a physically unavailable
UART and does not configure host firewall or interfaces.

## Independent protocol and orchestration checks

`test_tftp_readonly.py` uses real UDP sockets and the independent curl TFTP
client. Two sequential immutable snapshots, negotiated options, exact-length
EOF, lost ACK retransmission, stale ACK behavior, missing ACK failure,
foreign-peer exclusion, total request deadline, worker shutdown and denied
WRQ/path/out-of-order requests are checked. File bytes and SHA match exactly.

`test_ram_boot_tftp.py` combines that actual curl/UDP download with a Linux
serial PTY and the real checked diagnostic kernel/placement plan. It verifies
temporary variables, filesize/CRC, restored environment and final boot ordering.
A small external-rootfs fixture independently exercises two-file orchestration;
it does not substitute for the application profile's structural/QEMU checks.
Loopback addressing and UART responses are test fixtures, not hardware evidence.

Failures in DDR, live setenv syntax, filesize, CRC, restored values and console
response all prevent boot. A lost console receives no recovery commands.
Earlier YMODEM/existing-RAM device gates retain their regression checks.

Local `make lint`, `make build`, `make test` and `make test-serial` passed.
The expanded six TFTP orchestration cases passed, including second-image
size/CRC failures and restoring an originally enabled autostart policy.
The eight independent UDP/curl cases also passed natively on Windows.

The actual current router kernel (3436528 bytes, SHA-256
`33e303e41528d8eefd3c192d4fe1c9d2286d702222d41bf29479f4c22560d4c8`)
and external initrd (21044278 bytes, SHA-256
`bca90c4678b8623446dcaf914a2dcb7d4e3409c2ef43e1e9dcc9248210310b0d`)
were each transferred in full through Windows loopback with curl. Both the
plain 512-byte protocol and negotiated 1468-byte blocks matched every byte
and completion hash. Marker: `TFTP_LOCAL_ROUTER_SNAPSHOT_PASS`. These local
transfer times are not board network-performance measurements.

The complete diagnostic [run 38307787289](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38307787289)
passed on `164fc1801e814aa33b9c7b24b284b5251aa7dab7`, including the real
UDP/curl suite, UART PTY orchestration, core regression and all separate
diagnostic profiles. The actual Actions job and every step were inspected;
see [remote acceptance](diagnostic-ci-20261013.md). Physical TFTP and normal
OpenWrt startup/throughput remain untested.
