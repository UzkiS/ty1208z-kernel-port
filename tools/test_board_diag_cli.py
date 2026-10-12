#!/usr/bin/env python3
"""Verify diagnostic-shell identity gates and bounded capture on Linux PTYs."""
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

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration runs on Linux")
class DiagnosticTests(unittest.TestCase):
    def exercise(self, mode, profile="diag1"):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "capture"
            master, slave = os.openpty()
            errors = []
            commands = []

            def read_command():
                incoming = bytearray()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.05)[0]:
                        data = os.read(master, 1)
                        incoming.extend(data)
                        if data == b"\r":
                            commands.append(bytes(incoming))
                            return bytes(incoming)
                raise AssertionError("No command received")

            def peer():
                try:
                    self.assertEqual(read_command(), b"\r")
                    if mode == "bootloader":
                        os.write(master, b"\r\nfastboot# ")
                        return
                    os.write(master, b"\r\n# ")
                    self.assertEqual(read_command(), b"uname -r\r")
                    kernel = b"4.4.35" if mode == "wrong-kernel" else b"6.12.112-ty1208z-" + profile.encode()
                    os.write(master, b"uname -r\r\n" + kernel + b"\r\n# ")
                    if mode == "wrong-kernel":
                        return
                    self.assertEqual(read_command(), b"diag; echo TY1208Z_DIAG_COMPLETE\r")
                    time64 = b"TIME64_FAIL" if mode == "probe-failure" else b"TIME64_PASS sizeof(time_t)=8 file=2208988800"
                    audit = b"EMMC_AUDIT_READ_ONLY_COMPLETE" if mode != "missing-audit" else b"No audit driver"
                    # Fragment the output to exercise prompt/marker reassembly.
                    for part in (b"diag; echo TY1208Z_DIAG_COMPLETE\r\n", time64,
                                 b"\r\ndiagnostic output\r\n" * 1024,
                                 b"\r\n" + audit,
                                 b"\r\nTY1208Z_DIAG_", b"COMPLETE\r\n# "):
                        os.write(master, part)
                        time.sleep(0.01)
                except BaseException as exc:
                    errors.append(exc)

            process = subprocess.Popen([
                sys.executable, "-u", str(ROOT / "tools/board_diag_cli.py"),
                "--port", os.ttyname(slave), "--output", str(prefix),
                "--profile", profile,
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                output, _ = process.communicate(timeout=15)
                thread.join(timeout=8)
                self.assertFalse(thread.is_alive())
                if errors:
                    raise errors[0]
                self.assertFalse(select.select([master], [], [], 0.05)[0], "Unexpected extra command")
                self.assertEqual(process.returncode, 0 if mode == "success" else 1, output.decode())
                report = json.loads(prefix.with_suffix(".json").read_text())
                self.assertEqual(report["report_complete"], mode == "success")
                self.assertEqual(len(commands), 1 if mode == "bootloader" else 2 if mode == "wrong-kernel" else 3)
                if mode == "success":
                    self.assertIn(b"file=2208988800", prefix.with_suffix(".rx").read_bytes())
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                thread.join(timeout=8)
                os.close(master)
                os.close(slave)

    def test_bootloader_prompt_sends_no_shell_commands(self):
        self.exercise("bootloader")

    def test_wrong_kernel_sends_no_diagnostic_command(self):
        self.exercise("wrong-kernel")

    def test_probe_failure_is_not_success(self):
        self.exercise("probe-failure")

    def test_complete_fragmented_report_is_captured(self):
        self.exercise("success")

    def test_emmc_profile_requires_audit_completion(self):
        self.exercise("missing-audit", profile="emmc-audit1")

    def test_emmc_profile_captures_completed_audit(self):
        self.exercise("success", profile="emmc-audit1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
