#!/usr/bin/env python3
"""Exercise temporary DHCP/ping only in the exact RAM Ethernet candidate."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from board_diag_cli import ShellExchange, shell_command
from serial_cli import open_receiver
from ymodem_sender import TransferError


def run(args, serial_module):
    started = datetime.now(timezone.utc)
    prefix = args.output or Path(__file__).resolve().parents[1] / "evidence" / started.strftime("ethernet-net-%Y%m%dT%H%M%S.%fZ")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {kind: Path(str(prefix) + suffix) for kind, suffix in (
        ("raw", ".rx"), ("journal", ".tx.jsonl"), ("metadata", ".json"))}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Output exists; choose a fresh prefix")
    result = {"schema": 1, "port": args.port, "started_utc": started.isoformat(),
              "status": "starting", "kernel_verified": False, "dhcp_ping_pass": False}
    with open_receiver(serial_module, args.port, 115200, 0.02) as port:
        with paths["raw"].open("xb") as raw, paths["journal"].open("x", encoding="utf-8") as journal:
            exchange = ShellExchange(port, raw, journal)
            try:
                shell_command(exchange, b"")
                identity = shell_command(exchange, b"uname -r")
                if not re.search(rb"(?:^|[\r\n])6\.12\.112-ty1208z-ethernet-net1[\r\n]", identity):
                    raise TransferError("Kernel differs; network configuration not sent")
                result["kernel_verified"] = True
                report = shell_command(exchange, b"ethernet-diag --dhcp; echo TY1208Z_ETHERNET_COMPLETE", timeout=45)
                if not re.search(rb"(?:^|[\r\n])ETH_NET_DHCP_PING_PASS[\r\n]", report):
                    raise TransferError("DHCP/ping did not pass; inspect the captured report")
                result["dhcp_ping_pass"] = True
                result["status"] = "dhcp-ping-passed"
            except (TransferError, OSError, serial_module.SerialException, KeyboardInterrupt) as exc:
                result["status"] = "error"
                result["error"] = str(exc) or "Host interrupted"
                print(f"STOP: {result['error']}", file=sys.stderr, flush=True)
            finally:
                result.update({"ended_utc": datetime.now(timezone.utc).isoformat(),
                               "received_bytes": exchange.rx_bytes, "raw_sha256": exchange.digest.hexdigest()})
                with paths["metadata"].open("x", encoding="utf-8") as meta:
                    json.dump(result, meta, indent=2)
                    meta.write("\n")
    print(f"Port released; result={result['status']}; raw={paths['raw']}", flush=True)
    return 0 if result["dhcp_ping_pass"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    import serial
    try:
        return run(args, serial)
    except (ValueError, OSError, serial.SerialException) as exc:
        print(f"Ethernet diagnostic unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
