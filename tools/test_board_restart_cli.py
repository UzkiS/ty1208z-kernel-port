#!/usr/bin/env python3
"""PTY integration: identity gates, failed reset and actual fresh loader inspection."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from bootloader_probe import BootloaderProbe

ROOT = Path(__file__).resolve().parents[1]


class RestartSerialTests(unittest.TestCase):
    def exercise(self, mode):
        with tempfile.TemporaryDirectory(prefix="restart-cli-") as directory:
            prefix = Path(directory) / "capture"
            master, slave = pty.openpty()
            errors = []
            sent = []

            def read_command():
                buffer = bytearray()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        buffer.extend(os.read(master, 1))
                        if buffer.endswith(b"\r") or buffer == b"\x03":
                            sent.append(bytes(buffer))
                            return bytes(buffer)
                raise AssertionError("No expected command")

            def peer():
                try:
                    self.assertEqual(read_command(), b"\r")
                    if mode == "bootloader":
                        os.write(master, b"\r\nfastboot# ")
                        return
                    os.write(master, b"\r\n# ")
                    self.assertEqual(read_command(), b"uname -r\r")
                    release = b"4.4.35_ecoo" if mode == "hinas" else b"6.12.112-ty1208z-restart1"
                    os.write(master, b"uname -r\r\n" + release + b"\r\n# ")
                    if mode == "hinas":
                        return
                    self.assertEqual(read_command(), b"dmesg; echo TY1208Z_RESTART_CHECK_COMPLETE\r")
                    registration = b"not registered" if mode == "missing" else (
                        b"[0.4] driver: TY1208Z_RESTART_READY no-startup-writes explicit-restart-only")
                    completion = (b"dmesg; echo TY1208Z_RESTART_CHECK_COMPLETE" if mode == "echo-completion"
                                  else b"TY1208Z_RESTART_CHECK_COMPLETE")
                    os.write(master, registration + b"\r\n" + completion + b"\r\n# ")
                    if mode in {"missing", "echo-completion"}:
                        return
                    self.assertEqual(read_command(), b"reboot -f\r")
                    if mode == "failed":
                        os.write(master, b"Reboot fai")
                        time.sleep(0.03)
                        os.write(master, b"led -- System halted\r\n")
                        return
                    os.write(master, b"Bootrom start\r\nFastboot 3.3.0-dirty (test)\r\n"
                             b"CPU: Hi3798Mv100 (CA)\r\nReserve Memory\r\n")
                    self.assertEqual(read_command(), b"\x03")
                    os.write(master, b"\r\nfastboot# ")
                    for command in BootloaderProbe.COMMANDS:
                        self.assertEqual(read_command(), command)
                        os.write(master, command + b"\r\nread-only reply\r\nfastboot# ")
                except BaseException as exc:
                    errors.append(exc)

            process = subprocess.Popen([
                sys.executable, "-u", str(ROOT / "tools/board_restart_cli.py"),
                "--port", os.ttyname(slave), "--output", str(prefix), "--timeout", "5",
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                output, _ = process.communicate(timeout=15)
                thread.join(timeout=9)
                self.assertFalse(thread.is_alive())
                if errors:
                    raise errors[0]
                self.assertEqual(process.returncode, 0 if mode == "success" else 1, output.decode())
                self.assertFalse(select.select([master], [], [], 0.05)[0], "Extra command")
                report = json.loads(prefix.with_suffix(".json").read_text())
                self.assertEqual(report["restart_sent"], mode in {"success", "failed"})
                if mode == "success":
                    self.assertEqual(report["probe"]["completed_commands"], len(BootloaderProbe.COMMANDS))
                    self.assertEqual(report["status"], "restart-bootloader-verified")
                self.assertFalse(report["persistent_writes"])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                os.close(slave)

    def test_foreign_system_and_missing_registration_get_no_restart(self):
        for mode in ("bootloader", "hinas", "missing", "echo-completion"):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_failed_reset_is_not_retried(self):
        self.exercise("failed")

    def test_fresh_bootloader_is_identified_and_inspected(self):
        self.exercise("success")


if __name__ == "__main__":
    unittest.main(verbosity=2)
