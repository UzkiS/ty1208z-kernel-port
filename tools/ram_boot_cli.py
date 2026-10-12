#!/usr/bin/env python3
"""Transfer one validated diagnostic to measured RAM, CRC-check, optionally boot."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from bootloader_probe import BootloaderProbe
from prepare_ram_boot import ADDRESS, prepare
from openwrt_apps_ram_profile import INITRD_ADDRESS
from serial_cli import console_text, open_receiver
from ymodem_sender import TransferError, YmodemSender


class Exchange:
    def __init__(self, port, raw, journal):
        self.port = port
        self.raw = raw
        self.journal = journal
        self.digest = hashlib.sha256()
        self.rx_bytes = 0

    def read(self, size):
        data = self.port.read(size)
        if data:
            self.raw.write(data)
            self.raw.flush()
            self.digest.update(data)
            self.rx_bytes += len(data)
        return data

    def write(self, data):
        record = {"utc": datetime.now(timezone.utc).isoformat(), "bytes": len(data),
                  "sha256": hashlib.sha256(data).hexdigest(), "status": "attempted"}
        if len(data) < 128:
            record["hex"] = data.hex()
        self.journal.write(json.dumps(record) + "\n")
        if self.port.write(data) != len(data):
            raise TransferError("Partial serial write; no retry or boot")
        self.journal.write(json.dumps({**record, "status": "written"}) + "\n")
        self.journal.flush()

    def until(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        response = bytearray()
        while time.monotonic() < deadline:
            data = self.read(1)
            if data:
                response.extend(data)
                if len(response) > 65536:
                    raise TransferError("Console response exceeded limit")
                if predicate(bytes(response)):
                    return bytes(response)
        raise TransferError("Console response timeout; no further command or boot")

    def command(self, command):
        self.write(command.encode("ascii") + b"\r")
        response = self.until(lambda data: BootloaderProbe.PROMPT.search(data))
        print(console_text(response.decode("utf-8", "backslashreplace")), end="", flush=True)
        return response


def load_image(exchange, plan, data):
    address = plan.get("address", plan.get("header_address"))
    if (not isinstance(address, int) or address not in (ADDRESS, INITRD_ADDRESS) or
            plan.get("load_command") != f"loady {address:x} 115200"):
        raise TransferError("Validated transfer address/command differs; nothing sent")
    exchange.write(plan["load_command"].encode("ascii") + b"\r")
    announcement = f"download to 0x{address:08X} at 115200 bps...".encode()
    ready = exchange.until(lambda response: announcement in response)
    print(console_text(ready.decode("utf-8", "backslashreplace")), flush=True)
    last_progress = time.monotonic()

    def progress(done, total):
        nonlocal last_progress
        if done == total or time.monotonic() - last_progress >= 15:
            print(f"YMODEM {done}/{total} bytes ({done * 100 // total}%)", flush=True)
            last_progress = time.monotonic()

    YmodemSender(exchange, progress=progress).send(data)
    receipt = exchange.until(lambda response: BootloaderProbe.PROMPT.search(response), timeout=15)
    print(console_text(receipt.decode("utf-8", "backslashreplace")), flush=True)
    match = re.search(rb"## Total Size\s*=\s*0x([0-9a-fA-F]+)\s*=\s*(\d+) Bytes", receipt)
    if not match or int(match[1], 16) != len(data) or int(match[2]) != len(data):
        raise TransferError("Reported transfer size differs; no boot")


def run(args, serial_module):
    # Rebuild the plan from current artifacts and verified raw inspection. No
    # caller-selected address or arbitrary bootloader command is accepted.
    plan = prepare(args.artifacts, args.inspection)
    data = (args.artifacts / "uImage-UNTESTED.bin").read_bytes()
    started = datetime.now(timezone.utc)
    prefix = args.output or Path(__file__).resolve().parents[1] / "evidence" / started.strftime("ram-boot-%Y%m%dT%H%M%S.%fZ")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {key: Path(str(prefix) + suffix) for key, suffix in (
        ("raw", ".rx"), ("journal", ".tx.jsonl"), ("metadata", ".json"),
    )}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Output already exists; choose a fresh prefix")
    result = {"schema": 1, "started_utc": started.isoformat(), "port": args.port,
              "plan": plan, "status": "starting", "ram_crc_verified": False, "boot_sent": False,
              "transfer_requested": not args.boot_existing}
    exchange = None
    with open_receiver(serial_module, args.port, 115200, 0.02) as port:
        with paths["raw"].open("xb") as raw, paths["journal"].open("x", encoding="utf-8") as journal:
            exchange = Exchange(port, raw, journal)
            try:
                print(f"READY {args.port}: measured RAM candidate, {len(data)} bytes, SHA256 {plan['image_sha256']}", flush=True)
                exchange.command("")
                version = exchange.command("version")
                if not re.search(rb"(?:^|[\r\n])Fastboot 3\.3\.0-dirty ", version):
                    raise TransferError("Bootloader identity differs; no RAM transfer")
                ddr = exchange.command("getinfo ddrfree")
                if b"DDR free region baseaddr:0x1000000 size:0x3F000000" not in ddr:
                    raise TransferError("DDR bounds differ; no RAM transfer")
                bootcmd = exchange.command("printenv bootcmd")
                if b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0" not in bootcmd:
                    raise TransferError("Existing boot path differs; no RAM transfer")
                if not args.boot_existing:
                    load_image(exchange, plan, data)
                crc = exchange.command(plan["crc_command"])
                match = re.search(rb"CRC32 for [^\r\n]*==>\s*([0-9a-fA-F]{8})", crc)
                if not match or match[1].decode().lower() != plan["image_crc32"]:
                    raise TransferError("RAM CRC32 differs; no boot")
                result["verified_files"] = [{"file": "uImage-UNTESTED.bin", "crc32": plan["image_crc32"]}]
                for item in plan.get("additional_loads", []):
                    rootfs = (args.artifacts / item["file"]).read_bytes()
                    if len(rootfs) != item["bytes"] or hashlib.sha256(rootfs).hexdigest() != item["sha256"]:
                        raise TransferError("External initrd changed after planning; no transfer or boot")
                    if not args.boot_existing:
                        load_image(exchange, item, rootfs)
                    crc = exchange.command(item["crc_command"])
                    match = re.search(rb"CRC32 for [^\r\n]*==>\s*([0-9a-fA-F]{8})", crc)
                    if not match or match[1].decode().lower() != item["image_crc32"]:
                        raise TransferError("External initrd RAM CRC32 differs; no boot")
                    result["verified_files"].append({"file": item["file"], "crc32": item["image_crc32"]})
                result["ram_crc_verified"] = True
                result["status"] = "ram-verified"
                print("RAM IMAGE CRC VERIFIED" + ("; EXTERNAL INITRD VERIFIED" if plan.get("additional_loads") else ""), flush=True)
                if args.boot:
                    exchange.write(plan["boot_command"].encode("ascii") + b"\r")
                    result["boot_sent"] = True
                    result["status"] = "boot-sent"
                    end = time.monotonic() + args.capture_seconds
                    while time.monotonic() < end:
                        incoming = exchange.read(min(max(port.in_waiting, 1), 4096))
                        if incoming:
                            print(console_text(incoming.decode("utf-8", "backslashreplace")), end="", flush=True)
                    # Preserve a truthful distinction between sending bootm and
                    # proving a usable board-specific diagnostic shell.
            except (TransferError, OSError, serial_module.SerialException, KeyboardInterrupt) as exc:
                result["status"] = "error"
                result["error"] = str(exc) or "Host interrupted"
                print(f"STOP: {result['error']}; no automatic reconnect or further boot", file=sys.stderr, flush=True)
            finally:
                result.update({"ended_utc": datetime.now(timezone.utc).isoformat(),
                               "received_bytes": exchange.rx_bytes, "raw_sha256": exchange.digest.hexdigest()})
                with paths["metadata"].open("x", encoding="utf-8") as meta:
                    json.dump(result, meta, indent=2)
                    meta.write("\n")
    print(f"Port released; result={result['status']}; raw={paths['raw']}", flush=True)
    return 1 if result["status"] == "error" else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--boot", action="store_true", help="Boot only after successful transfer size and RAM CRC checks")
    parser.add_argument("--boot-existing", action="store_true", help="Skip transfer; recheck current RAM CRC before boot")
    parser.add_argument("--capture-seconds", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.capture_seconds <= 600:
        parser.error("capture-seconds must be 1..600")
    if args.boot_existing:
        args.boot = True
    import serial
    try:
        return run(args, serial)
    except (ValueError, OSError, serial.SerialException) as exc:
        print(f"RAM diagnostic unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
