#!/usr/bin/env python3
"""PTY integration: native identity, real completion markers and bounded server."""
import json
import os
from pathlib import Path
import select
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from openwrt_ethernet_board_cli import (
    PROFILES, SOURCE_REVISION, DT_IDENTITY, REPORT, START_IPERF, COLLECT_IPERF, iperf_summary,
)
from ymodem_sender import TransferError

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration needs Linux")
class NativeSerialTests(unittest.TestCase):
    def exercise(self, mode, operation="report", profile="net"):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "native"
            master, slave = os.openpty()
            commands, errors = [], []
            prompt = b"\r\nroot@OpenWrt:/# "

            def receive():
                data = bytearray()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.05)[0]:
                        data.extend(os.read(master, 1))
                        if data.endswith(b"\r"):
                            commands.append(bytes(data))
                            return bytes(data)
                raise AssertionError("Expected native command missing")

            def peer():
                try:
                    self.assertEqual(receive(), b"\r")
                    os.write(master, b"\r\nfastboot# " if mode == "bootloader" else prompt)
                    if mode == "bootloader":
                        return
                    self.assertEqual(receive(), b"uname -r; cat /etc/openwrt_release\r")
                    release, target, compatible = PROFILES[profile]
                    revision = b"source-foreign" if mode == "wrong-source" else SOURCE_REVISION
                    if mode == "wrong-kernel":
                        release = b"4.4.35"
                    if mode == "wrong-rootfs":
                        target = b"hi3798mv100/apps" if profile == "net" else b"hi3798mv100/net"
                    os.write(master, b"\r\n" + release + b"\r\nDISTRIB_ID='OpenWrt'\r\nDISTRIB_REVISION='"
                             + revision + b"'\r\nDISTRIB_TARGET='" + target + b"'" + prompt)
                    if mode in ("wrong-kernel", "wrong-rootfs", "wrong-source"):
                        return
                    self.assertEqual(receive(), DT_IDENTITY + b"\r")
                    if mode == "wrong-board":
                        compatible = b"linux,dummy-virt"
                    if mode == "missing-board":
                        compatible = b""
                    os.write(master, b"\r\n" + compatible + prompt)
                    if mode in ("wrong-board", "missing-board"):
                        return
                    payload, marker = {
                        "report": (REPORT, b"OPENWRT_ETHERNET_BOARD_PASS"),
                        "iperf-start": (START_IPERF, b"OPENWRT_IPERF_READY"),
                        "iperf-collect": (COLLECT_IPERF, b"OPENWRT_IPERF_FINISHED"),
                    }[operation]
                    self.assertEqual(receive(), b"rm -f /tmp/ty1208z-native-test.sh\r")
                    os.write(master, prompt)
                    encoded = bytearray()
                    while True:
                        transmitted = receive()
                        self.assertLess(len(transmitted), 256)
                        if transmitted == b"sh /tmp/ty1208z-native-test.sh\r":
                            break
                        self.assertTrue(transmitted.startswith(b"printf %b '") and transmitted.endswith(b"' >> /tmp/ty1208z-native-test.sh\r"))
                        encoded.extend(int(value, 8) for value in re.findall(rb"\\0([0-7]{3})", transmitted.split(b"'")[1]))
                        os.write(master, prompt)
                    self.assertEqual(bytes(encoded), payload + b"\n")
                    report = (b"echo " + marker + b"\r\n" if mode == "echo-only" else marker + b"\r\n")
                    if operation == "report" and mode != "missing-binding":
                        report += (b"ETH_NET_CLOCK_ENABLED crg51=0000000b inherited-phy\r\n"
                                   b"ETH_NET_PHY_VERIFIED id=20669823 inherited-no-reset\r\n"
                                   b"phy_id=0x20669823, phy_mode=mii\r\nTIME64_PASS sizeof(time_t)=8\r\n")
                    if operation == "iperf-collect":
                        report += (b'{\r\n"start":{"version":"iperf 3.20"},'
                                   b'"end":{"sum_received":{"bytes":1048576,"bits_per_second":8388608}}\r\n}\r\n')
                    os.write(master, b"\r\n" + report + b"TY1208Z_OPENWRT_COMPLETE" + prompt)
                except BaseException as exc:
                    errors.append(exc)

            flags = {"report": [], "iperf-start": ["--iperf-start"], "iperf-collect": ["--iperf-collect"]}[operation]
            process = subprocess.Popen([sys.executable, "-u", str(ROOT / "tools/openwrt_ethernet_board_cli.py"),
                                        "--port", os.ttyname(slave), "--profile", profile,
                                        "--output", str(prefix), *flags],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                output, _ = process.communicate(timeout=15)
                thread.join(timeout=8)
                self.assertFalse(thread.is_alive())
                if errors:
                    raise errors[0]
                self.assertFalse(select.select([master], [], [], 0.05)[0], "Unexpected additional command")
                passed = mode == "success"
                self.assertEqual(process.returncode, 0 if passed else 1, output.decode())
                metadata = json.loads(prefix.with_suffix(".json").read_text())
                self.assertEqual(metadata["operation"], operation)
                self.assertEqual(metadata["profile"], profile)
                self.assertEqual(metadata["status"], operation + "-passed" if passed else "error")
                if passed and operation == "iperf-collect":
                    self.assertEqual(metadata["iperf_summary"]["sum_received"]["bytes"], 1048576)
                if mode == "bootloader":
                    self.assertEqual(len(commands), 1)
                elif mode in ("wrong-kernel", "wrong-rootfs", "wrong-source"):
                    self.assertEqual(len(commands), 2)
                elif mode in ("wrong-board", "missing-board"):
                    self.assertEqual(len(commands), 3)
                else:
                    self.assertGreater(len(commands), 4)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                thread.join(timeout=8)
                os.close(master)
                os.close(slave)

    def test_refuses_bootloader_and_foreign_kernel_rootfs(self):
        for mode in ("bootloader", "wrong-kernel", "wrong-rootfs", "wrong-source", "wrong-board", "missing-board"):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_report_requires_output_marker_and_binding(self):
        for mode in ("echo-only", "missing-binding", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_one_off_server_operations(self):
        for operation in ("iperf-start", "iperf-collect"):
            with self.subTest(operation=operation):
                self.exercise("success", operation)

    def test_integrated_profile_rejects_foreign_kernel_rootfs(self):
        for mode in ("wrong-kernel", "wrong-rootfs", "wrong-source", "wrong-board", "missing-board", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode, profile="router")


class IperfResultTests(unittest.TestCase):
    def test_rejects_error_empty_and_echoed_json(self):
        for report in (
            b'echo {"start":{"version":"iperf 3.20"},"end":{"sum_received":{"bytes":1}}}',
            b'{"start":{"version":"iperf 3.20"},"error":"idle timeout"}',
            b'{"start":{"version":"iperf 3.20"},"end":{"sum_received":{"bytes":0}}}',
            b'{"start":{"version":"iperf 3.19"},"end":{"sum_received":{"bytes":1}}}',
        ):
            with self.subTest(report=report), self.assertRaises(TransferError):
                iperf_summary(report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
