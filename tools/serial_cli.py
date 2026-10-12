#!/usr/bin/env python3
"""List serial ports and capture UART RX without transmitting device commands."""
import argparse
import codecs
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time


def open_receiver(serial_module, port, baud):
    receiver = serial_module.Serial(
        port=None, baudrate=baud, bytesize=8, parity="N", stopbits=1,
        timeout=0.2, xonxoff=False, rtscts=False, dsrdtr=False,
        exclusive=True if os.name == "posix" else None,
    )
    # Set before open: pyserial otherwise defaults DTR/RTS to asserted.
    receiver.dtr = False
    receiver.rts = False
    receiver.port = port
    try:
        receiver.open()
    except Exception:
        receiver.close()
        raise
    return receiver


def console_text(text):
    # Preserve logs, but do not let device bytes execute host terminal escapes.
    return "".join(
        char if char in "\r\n\t" or (char.isprintable() and char != "\x7f")
        else f"\\x{ord(char):02x}"
        for char in text
    )


def capture(args, serial_module):
    started = datetime.now(timezone.utc)
    if args.stop_file is not None and args.stop_file.exists():
        raise ValueError(f"Stop file already exists; choose a fresh path: {args.stop_file}")
    prefix = args.output or (
        Path(__file__).resolve().parents[1] / "evidence"
        / ("ttl-cli-" + started.strftime("%Y%m%dT%H%M%S.%fZ"))
    )
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {key: Path(str(prefix) + suffix) for key, suffix in (
        ("raw", ".rx"), ("text", ".txt"), ("metadata", ".json"),
    )}
    if any(path.exists() for path in paths.values()):
        raise ValueError(f"Output already exists; choose a fresh prefix: {prefix}")
    receiver = open_receiver(serial_module, args.port, args.baud)
    count = 0
    digest = hashlib.sha256()
    reason = "error"
    failure = None
    decoder = codecs.getincrementaldecoder("utf-8")("backslashreplace")
    metadata = {
        "schema": 1, "mode": "receive-only", "port": args.port,
        "baud": args.baud, "data_bits": 8, "parity": "none", "stop_bits": 1,
        "flow_control": "none", "dtr": False, "rts": False,
        "started_utc": started.isoformat(), "status": "capturing",
        "raw_file": paths["raw"].name, "text_file": paths["text"].name,
    }
    # Output creation is exclusive; never overwrite an earlier hardware report.
    try:
        with paths["raw"].open("xb") as raw, paths["text"].open(
            "x", encoding="utf-8", newline=""
        ) as text_log, paths["metadata"].open("x", encoding="utf-8") as meta:
            json.dump(metadata, meta, indent=2)
            meta.write("\n")
            meta.flush()
            print(f"READY {args.port} {args.baud} 8N1, no flow control, RX only", flush=True)
            print(f"Raw: {paths['raw']}\nText: {paths['text']}", flush=True)
            if args.stop_file is not None:
                print(f"Stop file: {args.stop_file.resolve()}", flush=True)
            deadline = time.monotonic() + args.duration if args.duration else None
            try:
                while True:
                    if args.stop_file is not None and args.stop_file.exists():
                        reason = "stop-file"
                        break
                    if deadline is not None and time.monotonic() >= deadline:
                        reason = "duration"
                        break
                    data = receiver.read(min(max(receiver.in_waiting, 1), 4096))
                    if not data:
                        continue
                    raw.write(data)
                    raw.flush()
                    digest.update(data)
                    count += len(data)
                    decoded = decoder.decode(data)
                    text_log.write(decoded)
                    text_log.flush()
                    sys.stdout.write(console_text(decoded))
                    sys.stdout.flush()
            except KeyboardInterrupt:
                reason = "keyboard-interrupt"
            except (serial_module.SerialException, OSError) as exc:
                failure = str(exc)
                reason = "serial-error"
            finally:
                tail = decoder.decode(b"", final=True)
                text_log.write(tail)
                text_log.flush()
                sys.stdout.write(console_text(tail))
                metadata.update({
                    "status": "stopped", "stop_reason": reason,
                    "ended_utc": datetime.now(timezone.utc).isoformat(),
                    "received_bytes": count, "raw_sha256": digest.hexdigest(),
                })
                if failure is not None:
                    metadata["error"] = failure
                meta.seek(0)
                meta.truncate()
                json.dump(metadata, meta, indent=2)
                meta.write("\n")
    finally:
        receiver.close()
    print(f"\nSTOP {reason}; received {count} bytes; port released", flush=True)
    if failure is not None:
        print(f"Serial receive failed: {failure}. No automatic reconnect.", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    # Windows redirected stdout can use a legacy code page; retain diagnostics.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    subparsers.add_parser("list", help="List present serial ports")
    receive = subparsers.add_parser("capture", help="Receive only; save raw/text logs locally")
    receive.add_argument("--port", required=True, help="COM5 on Windows, /dev/ttyUSB0 on Linux")
    receive.add_argument("--baud", type=int, default=115200)
    receive.add_argument("--duration", type=float, default=0, help="Seconds; 0 until Ctrl+C/stop file")
    receive.add_argument("--output", type=Path, help="New output prefix; defaults to evidence/UTC time")
    receive.add_argument("--stop-file", type=Path, help="Stop when this initially absent file appears")
    args = parser.parse_args(argv)
    if args.operation == "capture" and (
        args.baud <= 0 or not math.isfinite(args.duration) or args.duration < 0
    ):
        parser.error("baud must be positive and duration must be finite and nonnegative")
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("Install the pinned dependency: python -m pip install --require-hashes "
              "-r tools/requirements-serial.txt", file=sys.stderr)
        return 2
    try:
        if args.operation == "list":
            ports = sorted(list_ports.comports(), key=lambda item: item.device)
            for port in ports:
                identity = f"{port.vid:04x}:{port.pid:04x}" if port.vid is not None and port.pid is not None else "unknown"
                print(f"{port.device}\t{port.description}\tUSB={identity}")
            if not ports:
                print("No serial ports found.")
            return 0
        return capture(args, serial)
    except (serial.SerialException, OSError, ValueError) as exc:
        print(f"Serial capture unavailable: {exc}\nClose other users of this port "
              "(including HiTool terminal/HiBurn); verify the current port with 'list'.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
