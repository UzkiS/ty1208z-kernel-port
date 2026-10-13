#!/usr/bin/env python3
"""Exercise capture and guarded inspection against a Linux PTY, without hardware."""
import hashlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import serial
from serial_cli import console_text

CLI = Path(__file__).with_name("serial_cli.py")


class ConsoleEncodingTests(unittest.TestCase):
    def test_legacy_console_escapes_unrepresentable_device_text(self):
        output = io.TextIOWrapper(io.BytesIO(), encoding="gbk", errors="strict")
        with patch("sys.stdout", output):
            text = console_text("中文\u061f\x1b[31m\x00\r\n")
            self.assertEqual(text, "中文\\u061f\\x1b[31m\\x00\r\n")
            output.write(text)
            output.flush()

    def test_utf8_console_preserves_printable_unicode(self):
        output = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict")
        with patch("sys.stdout", output):
            self.assertEqual(console_text("中文\u061f\r\n"), "中文\u061f\r\n")


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

    def launch(self, *extra, operation="capture"):
        output = self.console.open("wb")
        self.addCleanup(output.close)
        process = subprocess.Popen([
            sys.executable, "-u", str(CLI), operation, "--port", self.port,
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

    def peer_read(self, expected):
        received = b""
        deadline = time.monotonic() + 5
        while len(received) < len(expected) and time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.1)[0]:
                received += os.read(self.master, 4096)
        self.assertEqual(received, expected)

    def test_probe_waits_for_fresh_boot_and_completes_queries(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        # A prompt or stale autoboot text alone must not authorize TX.
        os.write(self.master, b"fastboot# \r\nPress Ctrl+C to stop autoboot\r\n")
        self.assertFalse(select.select([self.master], [], [], 0.2)[0])
        for fragment in (
            b"\r\nBootrom sta", b"rt\r\nFastboot 3.3.0-dirty (vendor)\r\n",
            b"CPU: Hi3798Mv100 (CA)\r\nReserve Memory\r\n",
        ):
            os.write(self.master, fragment)
        self.peer_read(b"\x03")
        commands = (
            b"help\r", b"printenv bootcmd bootargs bootdelay loadaddr bootm_low bootm_size\r",
            b"help bootm\r", b"help tftp\r", b"help loadb\r",
        )
        for command in commands:
            # Split prompt delivery exercises actual serial stream boundaries.
            os.write(self.master, b"\r\nresponse\r\nfastbo")
            self.assertFalse(select.select([self.master], [], [], 0.03)[0])
            os.write(self.master, b"ot# ")
            self.peer_read(command)
        os.write(self.master, b"\r\nlast response\r\nfastboot# ")
        self.assertEqual(process.wait(timeout=5), 0, self.console.read_text())
        metadata = json.loads(self.prefix.with_suffix(".json").read_text())
        self.assertEqual(metadata["stop_reason"], "probe-complete")
        self.assertEqual(metadata["probe"]["completed_commands"], 5)
        records = [json.loads(line) for line in Path(str(self.prefix) + ".tx.jsonl").read_text().splitlines()]
        written = [bytes.fromhex(row["hex"]) for row in records if row["status"] == "written"]
        self.assertEqual(written, [b"\x03", *commands])

    def test_probe_rejects_different_board_without_transmitting(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Bootrom start\r\nFastboot 3.3.0-dirty (vendor)\r\n"
                 b"CPU: Hi3798Mv200 (CA)\r\nPress Ctrl+C to stop autoboot\r\n")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])
        self.assertEqual(Path(str(self.prefix) + ".tx.jsonl").read_bytes(), b"")

    def test_probe_accepts_full_ddr_sequence_when_bootrom_line_is_garbled(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"\xff\x00Initializing DDR ... OK\r\r\n"
                 b"Starting DDR training ... OK\r\r\nStarting fastboot ...\r\r\n"
                 b"Fastboot 3.3.0-dirty (vendor)\r\nCPU: Hi3798Mv100 (CA)\r\nReserve Memory\r\n")
        self.peer_read(b"\x03")
        from bootloader_probe import BootloaderProbe

        for command in BootloaderProbe.COMMANDS:
            os.write(self.master, b"\r\nfastboot# ")
            self.peer_read(command)
        os.write(self.master, b"\r\nfastboot# ")
        self.assertEqual(process.wait(timeout=5), 0)

    def test_probe_partial_ddr_and_version_do_not_allow_interrupt(self):
        process = self.launch("--duration", "0.4", operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Starting DDR training ... OK\r\nStarting fastboot ...\r\n"
                 b"Fastboot 3.3.0-dirty (vendor)\r\nCPU: Hi3798Mv100 (CA)\r\nReserve Memory\r\n")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_probe_ddr_sequence_still_requires_ca_identity(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Initializing DDR ... OK\r\nStarting DDR training ... OK\r\n"
                 b"Starting fastboot ...\r\nFastboot 3.3.0-dirty (vendor)\r\n"
                 b"CPU: Hi3798Mv200 (CA)\r\nReserve Memory\r\n")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_probe_ddr_restart_before_interrupt_transmits_nothing(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Initializing DDR ... OK\r\nStarting DDR training ... OK\r\n"
                 b"Starting fastboot ...\r\nFastboot 3.3.0-dirty (vendor)\r\n"
                 b"CPU: Hi3798Mv100 (CA)\r\nInitializing DDR ... OK\r\nReserve Memory\r\n")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_probe_expiry_at_linux_login_transmits_nothing(self):
        process = self.launch("--duration", "0.4", operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Ubuntu 24.04.4 LTS\r\nhi3798mv100 login: ")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_probe_stops_if_interrupt_did_not_stop_autoboot(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Bootrom start\r\nFastboot 3.3.0-dirty (vendor)\r\n"
                 b"CPU: Hi3798Mv100 (CA)\r\nPress Ctrl+C to stop autoboot\r\n")
        self.peer_read(b"\x03")
        os.write(self.master, b"\r\nStarting kernel ...\r\n")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_probe_rejects_late_autoboot_observation(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Bootrom start\r\nFastboot 3.3.0-dirty (vendor)\r\n"
                 b"CPU: Hi3798Mv100 (CA)\r\nPress Ctrl+C to stop autoboot\r\n"
                 b"Starting kernel ...\r\n")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_probe_stops_on_second_boot_before_autoboot(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Bootrom start\r\nFastboot 3.3.0-dirty (vendor)\r\n"
                 b"CPU: Hi3798Mv100 (CA)\r\nBootrom start\r\nReserve Memory\r\n")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_probe_stops_on_restart_after_interrupt(self):
        process = self.launch(operation="inspect-bootloader")
        self.ready(process)
        os.write(self.master, b"Bootrom start\r\nFastboot 3.3.0-dirty (vendor)\r\n"
                 b"CPU: Hi3798Mv100 (CA)\r\nReserve Memory\r\n")
        self.peer_read(b"\x03")
        os.write(self.master, b"Bootrom sta")
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])
        os.write(self.master, b"rt\r\nfastboot# ")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_attach_requires_prompt_and_version_before_queries(self):
        from bootloader_probe import BootloaderProbe

        process = self.launch(operation="inspect-current-bootloader")
        self.ready(process)
        self.peer_read(b"\r")
        os.write(self.master, b"\r\nfastbo")
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])
        os.write(self.master, b"ot# ")
        self.peer_read(b"version\r")
        os.write(self.master, b"\r\nFastboot 3.3.0-dirty (Dec 21 2016)\r\nfastboot# ")
        for command in BootloaderProbe.ATTACH_COMMANDS:
            self.peer_read(command)
            os.write(self.master, b"\r\nquery response\r\nfastboot# ")
        self.assertEqual(process.wait(timeout=5), 0, self.console.read_text())
        metadata = json.loads(self.prefix.with_suffix(".json").read_text())
        self.assertTrue(metadata["probe"]["attach"])
        self.assertFalse(metadata["probe"]["interrupt_sent"])
        self.assertEqual(metadata["probe"]["completed_commands"], len(BootloaderProbe.ATTACH_COMMANDS))

    def test_attach_at_linux_login_sends_no_command(self):
        process = self.launch(operation="inspect-current-bootloader")
        self.ready(process)
        self.peer_read(b"\r")
        os.write(self.master, b"\r\nhi3798mv100 login: ")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])

    def test_attach_rejects_different_version(self):
        process = self.launch(operation="inspect-current-bootloader")
        self.ready(process)
        self.peer_read(b"\r")
        os.write(self.master, b"\r\nfastboot# ")
        self.peer_read(b"version\r")
        os.write(self.master, b"\r\nFastboot 4.0\r\nfastboot# ")
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(select.select([self.master], [], [], 0.1)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
