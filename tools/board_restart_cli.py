#!/usr/bin/env python3
"""Explicitly restart only the identified SP805 RAM experiment and inspect its next boot."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

from board_diag_cli import ShellExchange, shell_command
from bootloader_probe import BootloaderProbe, ProbeError
from serial_cli import console_text, open_receiver
from ymodem_sender import TransferError


def run(args, serial_module):
    started = datetime.now(timezone.utc)
    prefix = args.output or Path(__file__).resolve().parents[1] / "evidence" / started.strftime("board-restart-%Y%m%dT%H%M%S.%fZ")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {key: Path(str(prefix) + suffix) for key, suffix in (
        ("raw", ".rx"), ("journal", ".tx.jsonl"), ("metadata", ".json"))}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Output exists; choose a fresh prefix")
    result = {"schema": 1, "port": args.port, "started_utc": started.isoformat(),
              "status": "starting", "kernel_verified": False, "restart_sent": False,
              "persistent_writes": False}
    probe = BootloaderProbe()
    with open_receiver(serial_module, args.port, 115200, 0.01) as port:
        with paths["raw"].open("xb") as raw, paths["journal"].open("x", encoding="utf-8") as journal:
            exchange = ShellExchange(port, raw, journal)
            try:
                shell_command(exchange, b"")
                identity = shell_command(exchange, b"uname -r")
                if not re.search(rb"(?:^|[\r\n])6\.12\.112-ty1208z-restart1[\r\n]", identity):
                    raise TransferError("Not the SP805 RAM experiment; no restart sent")
                result["kernel_verified"] = True
                report = shell_command(exchange, b"dmesg; echo TY1208Z_RESTART_CHECK_COMPLETE")
                if (not re.search(rb"(?:^|[\r\n])[^\r\n]*TY1208Z_RESTART_READY "
                                  rb"no-startup-writes explicit-restart-only[\r\n]", report) or
                        not re.search(rb"(?:^|[\r\n])TY1208Z_RESTART_CHECK_COMPLETE[\r\n]", report)):
                    raise TransferError("Actual restart registration missing; no restart sent")
                # PID 1 is the diagnostic shell, not an init service manager.
                # This fixed -f command enters the kernel restart syscall.
                exchange.write(b"reboot -f\r")
                result["restart_sent"] = True
                result["status"] = "restart-sent"
                deadline = time.monotonic() + args.timeout
                failure_tail = b""
                while not probe.finished:
                    if time.monotonic() >= deadline:
                        raise TransferError("No completed fresh bootloader inspection after restart")
                    probe.check_timeout()
                    data = exchange.read(min(max(port.in_waiting, 1), 4096))
                    if not data:
                        continue
                    print(console_text(data.decode("utf-8", "backslashreplace")), end="", flush=True)
                    failure_tail = (failure_tail + data)[-4096:]
                    if any(marker in failure_tail for marker in (
                            b"TY1208Z_RESTART_REFUSED", b"TY1208Z_RESTART_TIMEOUT", b"Reboot failed")):
                        raise TransferError("Kernel restart failed; no retry")
                    for outgoing in probe.feed(data):
                        exchange.write(outgoing)
                result["status"] = "restart-bootloader-verified"
            except (TransferError, ProbeError, OSError, serial_module.SerialException, KeyboardInterrupt) as exc:
                result.update(status="error", error=str(exc) or "Host interrupted")
                print(f"STOP: {result['error']}", file=sys.stderr, flush=True)
            finally:
                result.update(ended_utc=datetime.now(timezone.utc).isoformat(),
                              received_bytes=exchange.rx_bytes, raw_sha256=exchange.digest.hexdigest(),
                              probe=probe.snapshot())
                with paths["metadata"].open("x", encoding="utf-8") as metadata:
                    json.dump(result, metadata, indent=2)
                    metadata.write("\n")
    print(f"Port released; result={result['status']}; raw={paths['raw']}", flush=True)
    return 0 if result["status"] == "restart-bootloader-verified" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if not 5 <= args.timeout <= 120:
        parser.error("timeout must be 5..120 seconds")
    import serial
    try:
        return run(args, serial)
    except (OSError, ValueError, serial.SerialException) as exc:
        print(f"Restart UART unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
