#!/usr/bin/env python3
"""Test device-side CRC/DDR boot gates with built artifacts and a Linux PTY."""
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/diag1"


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration runs on Linux")
class BootGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.master, self.slave = os.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.raw = (b"Fastboot 3.3.0-dirty (vendor)\r\n"
                    b"DDR free region baseaddr:0x1000000 size:0x3F000000\r\n"
                    b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\r\n"
                    b"loady [ off ] [ baud ]\r\ncrc32 address count [addr]\r\n"
                    b"bootm [addr [arg ...]]\r\n")
        (self.root / "inspection.rx").write_bytes(self.raw)
        self.inspection = self.root / "inspection.json"
        self.inspection.write_text(json.dumps({"stop_reason": "probe-complete",
                                               "raw_file": "inspection.rx",
                                               "raw_sha256": hashlib.sha256(self.raw).hexdigest()}))
        self.image = (ARTIFACTS / "uImage-UNTESTED.bin").read_bytes()

    def read_command(self):
        received = bytearray()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.05)[0]:
                data = os.read(self.master, 1)
                received.extend(data)
                if data == b"\r":
                    return bytes(received)
        raise AssertionError(f"Command not received: {bytes(received)!r}")

    def exercise(self, wrong_crc=False, wrong_ddr=False):
        prefix = self.root / "attempt"
        console = self.root / "console.txt"
        errors = []
        boot = []

        def peer():
            try:
                for command, response in (
                    (b"\r", b""),
                    (b"version\r", b"Fastboot 3.3.0-dirty (vendor)"),
                    (b"getinfo ddrfree\r", b"DDR free region baseaddr:0x1000000 size:0x3F000000" if not wrong_ddr else b"DDR changed"),
                ):
                    self.assertEqual(self.read_command(), command)
                    os.write(self.master, b"\r\n" + response + b"\r\nfastboot# ")
                if wrong_ddr:
                    return
                self.assertEqual(self.read_command(), b"printenv bootcmd\r")
                os.write(self.master, b"\r\nbootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\r\nfastboot# ")
                self.assertEqual(self.read_command(), f"crc32 1ffffc0 {len(self.image):x}\r".encode())
                checksum = "00000000" if wrong_crc else f"{zlib.crc32(self.image):08x}"
                os.write(self.master, f"\r\nCRC32 for 01ffffc0 ... 0221f806 ==> {checksum}\r\nfastboot# ".encode())
                if not wrong_crc:
                    boot.append(self.read_command())
                    os.write(self.master, b"\r\nStarting kernel ...\r\nPTY_CAPTURE_SENTINEL\r\n")
            except BaseException as exc:
                errors.append(exc)

        with console.open("wb") as output:
            process = subprocess.Popen([
                sys.executable, "-u", str(ROOT / "tools/ram_boot_cli.py"),
                "--port", os.ttyname(self.slave), "--artifacts", str(ARTIFACTS),
                "--inspection", str(self.inspection), "--boot-existing",
                "--capture-seconds", "1", "--output", str(prefix),
            ], stdout=output, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                status = process.wait(timeout=15)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                thread.join(timeout=8)
        self.assertFalse(thread.is_alive())
        if errors:
            raise errors[0]
        self.assertFalse(select.select([self.master], [], [], 0.05)[0], "Unexpected additional bytes")
        self.assertEqual(status, 1 if wrong_crc or wrong_ddr else 0, console.read_text())
        result = json.loads(prefix.with_suffix(".json").read_text())
        self.assertFalse(result["transfer_requested"])
        self.assertEqual(result["boot_sent"], not (wrong_crc or wrong_ddr))
        self.assertEqual(boot, [] if wrong_crc or wrong_ddr else [b"bootm 1ffffc0\r"])
        if boot:
            self.assertIn(b"PTY_CAPTURE_SENTINEL", prefix.with_suffix(".rx").read_bytes())

    def test_crc_mismatch_never_boots(self):
        self.exercise(wrong_crc=True)

    def test_changed_ddr_never_checks_or_boots(self):
        self.exercise(wrong_ddr=True)

    def test_matching_crc_boots_once_and_captures(self):
        self.exercise()


if __name__ == "__main__":
    unittest.main(verbosity=2)
