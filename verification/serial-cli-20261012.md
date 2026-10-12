# Serial CLI validation — 2026-10-12

Scope: replace routine HiTool terminal/logging with a receive-only command-line
tool. No board commands, reboots, flashing or persistent boot changes were sent
by this tool. Raw local logs are ignored by Git.

## Local results

- Windows Python 3.13.15 with hash-locked pyserial 3.5: identified the current
  USB-SERIAL CH340 as COM5, USB ID `1a86:7523`.
- A one-second capture opened COM5 at 115200, 8N1, no flow control and released
  it normally. Zero bytes arrived during that idle interval; this establishes
  port access, not boot-log completeness or UART signal integrity.
- Linux/WSL `make lint` passed, including baseline LF/CRLF regression.
- `make test-serial`: six Linux pseudo-terminal integration tests passed:
  byte-exact streaming and split UTF-8 decoding with no host transmission;
  stop-file termination and port reuse; duration with no incoming data;
  output preservation; stale stop-file rejection; busy-port rejection; and
  peer disconnect retaining partial data and reporting failure. Several
  related assertions share a single test case.
- The byte-stream test includes CRLF, ANSI escape bytes, NUL, invalid UTF-8 and
  a truncated final UTF-8 sequence, and checks the recorded SHA-256.

## Limits

These checks do not validate the board's CA authentication, bootloader commands,
safe RAM ranges or the Linux 6.12 candidate on hardware. A complete original
boot log remains the next prerequisite. The tool currently has no transmit or
interactive mode; future bootloader command support must be added explicitly.

CI runs the PTY tests after installing the pinned serial dependency. Its actual
result must be checked after this change is pushed.
