#!/usr/bin/env python3
"""Verify no network commands reach Hinas/bootloader and no echoed false pass."""
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


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration needs Linux")
class EthernetTests(unittest.TestCase):
    def exercise(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "ethernet"
            master, slave = os.openpty()
            errors = []
            commands = []

            def receive():
                incoming = bytearray()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.05)[0]:
                        data = os.read(master, 1)
                        incoming.extend(data)
                        if data == b"\r":
                            commands.append(bytes(incoming))
                            return bytes(incoming)
                raise AssertionError("Command missing")

            def peer():
                try:
                    self.assertEqual(receive(), b"\r")
                    os.write(master, b"\r\nfastboot# " if mode == "bootloader" else b"\r\n# ")
                    if mode == "bootloader":
                        return
                    self.assertEqual(receive(), b"uname -r\r")
                    kernel = b"4.4.35" if mode == "wrong-kernel" else b"6.12.112-ty1208z-ethernet-net1"
                    os.write(master, b"uname -r\r\n" + kernel + b"\r\n# ")
                    if mode == "wrong-kernel":
                        return
                    self.assertEqual(receive(), b"ethernet-diag --dhcp; echo TY1208Z_ETHERNET_COMPLETE\r")
                    # An echoed substring cannot count as a successful script.
                    report = (b"ETH_NET_DHCP_BOUND\r\n4 packets transmitted, 4 received\r\n"
                              b"ETH_NET_DHCP_PING_PASS\r\n" if mode == "success" else
                              b"echo ETH_NET_DHCP_PING_PASS\r\nETH_NET_NO_GATEWAY\r\n")
                    os.write(master, report + b"TY1208Z_ETHERNET_COMPLETE\r\n# ")
                except BaseException as exc:
                    errors.append(exc)

            process = subprocess.Popen([
                sys.executable, "-u", str(ROOT / "tools/ethernet_board_cli.py"),
                "--port", os.ttyname(slave), "--output", str(prefix)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                output, _ = process.communicate(timeout=15)
                thread.join(timeout=8)
                self.assertFalse(thread.is_alive())
                if errors:
                    raise errors[0]
                self.assertFalse(select.select([master], [], [], 0.05)[0])
                self.assertEqual(process.returncode, 0 if mode == "success" else 1, output.decode())
                result = json.loads(prefix.with_suffix(".json").read_text())
                self.assertEqual(result["dhcp_ping_pass"], mode == "success")
                self.assertEqual(len(commands), 1 if mode == "bootloader" else 2 if mode == "wrong-kernel" else 3)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                thread.join(timeout=8)
                os.close(master)
                os.close(slave)

    def test_bootloader_sends_no_network_command(self):
        self.exercise("bootloader")

    def test_hinas_sends_no_network_command(self):
        self.exercise("wrong-kernel")

    def test_command_echo_cannot_fake_success(self):
        self.exercise("failed")

    def test_real_marker_captures_success(self):
        self.exercise("success")


if __name__ == "__main__":
    unittest.main(verbosity=2)
