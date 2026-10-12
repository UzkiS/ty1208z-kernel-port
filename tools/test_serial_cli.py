#!/usr/bin/env python3
"""Exercise the RX-only CLI against a Linux pseudo-terminal, without hardware."""
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest

import serial

CLI = Path(__file__).with_name("serial_cli.py")


def await_condition(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for the serial CLI")


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration runs on Linux")
class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.master, self.slave = os.openpty()
        self.addCleanup(lambda: os.close(self.master))
        self.addCleanup(os.close, self.slave)
        self.port = os.ttyname(self.slave)
        self.prefix = self.root / "capture"
        self.stop = self.root / "stop"
        self.console = self.root / "console.txt"

    def launch(self, *extra):
        output = self.console.open("wb")
        self.addCleanup(output.close)
        process = subprocess.Popen([
            sys.executable, "-u", str(CLI), "capture", "--port", self.port,
            "--output", str(self.prefix), "--stop-file", str(self.stop), *extra,
        ], stdout=output, stderr=subprocess.STDOUT)

        def cleanup():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

        self.addCleanup(cleanup)
        return process

    def ready(self, process):
        await_condition(lambda: b"READY " in self.console.read_bytes() or process.poll() is not None)
        self.assertIsNone(process.poll(), self.console.read_text())

    def test_byte_exact_streaming_stop_and_release(self):
        process = self.launch()
        self.ready(process)
        # The peer must receive no command, newline or other transmission.
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])
        chunks = [b"Boot\r\n\x1b[31m", b"\xe4\xb8", b"\xad\xff\x00", b"\xe2"]
        expected = b""
        for chunk in chunks:
            os.write(self.master, chunk)
            expected += chunk
            raw_path = self.prefix.with_suffix(".rx")
            await_condition(lambda: raw_path.read_bytes() == expected)
        # Data is flushed while the CLI is running; UTF-8 fragments survive.
        text_path = self.prefix.with_suffix(".txt")
        await_condition(lambda: "中\\xff" in text_path.read_text(encoding="utf-8"))
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])
        self.stop.touch()
        self.assertEqual(process.wait(timeout=5), 0, self.console.read_text())
        self.assertEqual(raw_path.read_bytes(), expected)
        self.assertEqual(text_path.read_bytes(), expected.decode("utf-8", "backslashreplace").encode())
        metadata = json.loads(self.prefix.with_suffix(".json").read_text())
        self.assertEqual(metadata["stop_reason"], "stop-file")
        self.assertEqual(metadata["received_bytes"], len(expected))
        self.assertEqual(metadata["raw_sha256"], hashlib.sha256(expected).hexdigest())
        self.assertEqual(metadata["mode"], "receive-only")
        console = self.console.read_bytes()
        self.assertNotIn(b"\x1b", console)
        self.assertIn(b"\\x1b[31m", console)
        with serial.Serial(self.port, 115200, timeout=0.1, exclusive=True):
            pass

    def test_duration_finishes_without_device_output(self):
        process = self.launch("--duration", "0.3")
        self.ready(process)
        self.assertEqual(process.wait(timeout=5), 0)
        metadata = json.loads(self.prefix.with_suffix(".json").read_text())
        self.assertEqual(metadata["stop_reason"], "duration")
        self.assertEqual(metadata["received_bytes"], 0)

    def test_existing_output_is_preserved(self):
        raw = self.prefix.with_suffix(".rx")
        raw.write_bytes(b"previous evidence")
        process = self.launch()
        self.assertEqual(process.wait(timeout=5), 2)
        self.assertEqual(raw.read_bytes(), b"previous evidence")
        self.assertFalse(self.prefix.with_suffix(".json").exists())

    def test_stale_stop_file_rejected(self):
        self.stop.touch()
        process = self.launch()
        self.assertEqual(process.wait(timeout=5), 2)
        self.assertFalse(self.prefix.with_suffix(".rx").exists())

    def test_busy_port_fails_without_capture(self):
        with serial.Serial(self.port, 115200, exclusive=True):
            process = self.launch()
            self.assertEqual(process.wait(timeout=5), 2)
        self.assertFalse(self.prefix.with_suffix(".rx").exists())

    def test_disconnect_preserves_received_bytes(self):
        process = self.launch()
        self.ready(process)
        os.write(self.master, b"partial boot\r\n")
        raw = self.prefix.with_suffix(".rx")
        await_condition(lambda: raw.read_bytes() == b"partial boot\r\n")
        # Simulate USB removal; retain a harmless fd for cleanup.
        os.close(self.master)
        self.master = os.open(os.devnull, os.O_RDONLY)
        self.assertEqual(process.wait(timeout=5), 1)
        metadata = json.loads(self.prefix.with_suffix(".json").read_text())
        self.assertEqual(metadata["stop_reason"], "serial-error")
        self.assertEqual(raw.read_bytes(), b"partial boot\r\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
