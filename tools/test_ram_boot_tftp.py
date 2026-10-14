"""Real UDP/curl plus serial PTY: temporary network rollback and CRC boot gates."""
import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zlib

from prepare_ram_boot import prepare
from ram_boot_cli import run
from ram_boot_tftp import TemporaryTftpNetwork, environment, network_addresses
from tftp_readonly import ReadOnlyTftp
from ymodem_sender import TransferError

ROOT = Path(__file__).resolve().parents[1]


class NetworkTests(unittest.TestCase):
    def test_addresses_and_environment_are_not_shell_text(self):
        self.assertEqual(network_addresses("192.0.2.10", "192.0.2.20"),
                         ("192.0.2.10", "192.0.2.20"))
        for host, board in (("192.0.2.10", "198.51.100.20"), ("192.0.2.1", "192.0.2.1"),
                            ("192.0.2.1", "192.0.2.0"), ("192.0.2.1", "192.0.2.255"),
                            ("169.254.1.1", "169.254.1.2"), ("192.0.2.1;reset", "192.0.2.2")):
            with self.subTest(host=host, board=board), self.assertRaises(ValueError):
                network_addresses(host, board)
        valid = (b'ipaddr=198.51.100.20\r\nserverip=198.51.100.10\r\n'
                 b'netmask=255.255.255.0\r\n## Error: "autostart" not defined\r\n')
        self.assertIsNone(environment(valid)["autostart"])
        for reply in (valid.replace(b"198.51.100.20", b"1;saveenv"),
                      valid + b"ipaddr=192.0.2.1\r\n", valid.replace(b'not defined', b'unknown'),
                      valid.replace(b"198.51.100.20", b"\xff")):
            with self.subTest(reply=reply), self.assertRaises(TransferError):
                environment(reply)

    def test_console_loss_never_sends_restore_commands(self):
        class LostConsole:
            prompt_known = False

            def command(self, _):
                raise AssertionError("Restore must not write to unknown console state")

        network = TemporaryTftpNetwork(LostConsole(), "192.0.2.10", "192.0.2.20")
        network.active = True
        network.restore()
        self.assertFalse(network.restored)
        self.assertIn("console-lost", network.restore_status)


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration needs Linux")
class BootTests(unittest.TestCase):
    def exercise(self, mode, external=False, autostart=None):
        import serial
        self.assertIsNotNone(shutil.which("curl"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = {"ipaddr": "198.51.100.20", "serverip": "198.51.100.10",
                        "netmask": "255.255.255.0", "autostart": autostart}
            settings = dict(original)
            artifacts = ROOT / "artifacts/diag1"
            raw = (b"Fastboot 3.3.0-dirty (vendor)\r\n"
                   b"DDR free region baseaddr:0x1000000 size:0x3F000000\r\n"
                   b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\r\n"
                   b"loady [ off ] [ baud ]\r\ncrc32 address count [addr]\r\n"
                   b"bootm [addr [arg ...]]\r\n")
            (root / "inspection.rx").write_bytes(raw)
            inspection = root / "inspection.json"
            inspection.write_text(json.dumps({"stop_reason": "probe-complete", "raw_file": "inspection.rx",
                                               "raw_sha256": hashlib.sha256(raw).hexdigest()}))
            actual_plan = prepare(artifacts, inspection)
            expected = {"ty1208z-uimage.bin": (artifacts / "uImage-UNTESTED.bin").read_bytes()}
            if external:
                # The real kernel/placement is validated above. A small independent
                # rootfs fixture checks orchestration; profile packaging has its own tests.
                fake = root / "artifacts"
                fake.mkdir()
                (fake / "uImage-UNTESTED.bin").write_bytes(expected["ty1208z-uimage.bin"])
                content = bytes(range(256)) * 6
                (fake / "initrd.bin").write_bytes(content)
                actual_plan["additional_loads"] = [{"address": 0x04000000, "file": "initrd.bin",
                    "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                    "image_crc32": f"{zlib.crc32(content):08x}",
                    "crc_command": f"crc32 4000000 {len(content):x}", "load_command": "loady 4000000 115200"}]
                expected["ty1208z-initrd.bin"] = content
                actual_plan["boot_command"] = "bootm 1ffffc0 4000000"
                artifacts = fake
            master, slave = os.openpty()
            errors, commands, servers, downloaded = [], [], [], []
            stop = threading.Event()
            filesize = 0

            def factory(address, peer, files):
                server = ReadOnlyTftp(address, peer, files, port=0,
                                      timeout=0.5 if mode == "lost-console" else 15)
                servers.append(server)
                return server

            def reply(payload=b""):
                os.write(master, b"\r\n" + payload + b"\r\nfastboot# ")

            def peer():
                nonlocal filesize
                try:
                    while not stop.is_set():
                        data = bytearray()
                        while not stop.is_set():
                            if select.select([master], [], [], 0.05)[0]:
                                data.extend(os.read(master, 1))
                                if data.endswith(b"\r"):
                                    break
                        if stop.is_set():
                            return
                        command = data[:-1].decode("ascii")
                        commands.append(command)
                        if command == "":
                            reply()
                        elif command == "version":
                            reply(b"Fastboot 3.3.0-dirty (vendor)")
                        elif command == "getinfo ddrfree":
                            reply(b"DDR changed" if mode == "wrong-ddr" else
                                  b"DDR free region baseaddr:0x1000000 size:0x3F000000")
                        elif command == "printenv bootcmd":
                            reply(b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0")
                        elif command == "help tftp":
                            reply(b"tftp [loadAddress] [bootfilename] <upload_size>")
                        elif command == "help setenv":
                            reply(b"unknown syntax" if mode == "unknown-setenv" else
                                  b"setenv name value ...\nsetenv name\n    - delete environment variable")
                        elif command.startswith("setenv "):
                            fields = command.split()
                            name = fields[1]
                            self.assertIn(name, original)
                            settings[name] = fields[2] if len(fields) == 3 else None
                            reply()
                        elif command == "printenv ipaddr serverip netmask autostart":
                            response = dict(settings)
                            if mode == "restore-mismatch" and downloaded and settings == original:
                                response["serverip"] = "192.0.2.99"
                            reply(b"\r\n".join((f'{name}={value}' if value is not None else
                                                 f'## Error: "{name}" not defined').encode()
                                                for name, value in response.items()))
                        elif command.startswith("tftp "):
                            if mode == "lost-console":
                                continue
                            self.assertEqual(settings["autostart"], "no")
                            _, address, alias = command.split()
                            self.assertEqual(address, "1ffffc0" if alias.endswith("uimage.bin") else "4000000")
                            destination = root / f"received-{len(downloaded)}"
                            server = servers[0]
                            subprocess.run(["curl", "--silent", "--show-error", "--fail", "--noproxy", "*",
                                            "--max-time", "10", f"tftp://127.0.0.1:{server.port}/{alias}",
                                            "--output", str(destination)], check=True, timeout=12)
                            self.assertEqual(destination.read_bytes(), expected[alias])
                            downloaded.append(alias)
                            filesize = len(expected[alias])
                            reply(b"TFTP transfer done")
                        elif command == "printenv filesize":
                            wrong = mode == "wrong-size" or (mode == "wrong-second-size" and len(downloaded) == 2)
                            reply(f"filesize={filesize + int(wrong):x}".encode())
                        elif command.startswith("crc32 "):
                            content = expected[downloaded[-1]]
                            wrong = mode == "wrong-crc" or (mode == "wrong-second-crc" and len(downloaded) == 2)
                            crc = 0 if wrong else zlib.crc32(content)
                            reply(f"CRC32 for RAM ==> {crc:08x}".encode())
                        elif command.startswith("bootm "):
                            self.assertEqual(settings, original)
                            self.assertEqual(command, actual_plan["boot_command"])
                            os.write(master, b"\r\nStarting kernel ...\r\nTFTP_PTY_CAPTURE\r\n")
                            return
                        else:
                            raise AssertionError(f"Unexpected command: {command}")
                except BaseException as exc:
                    errors.append(exc)

            args = argparse.Namespace(artifacts=artifacts, inspection=inspection, port=os.ttyname(slave),
                                      tftp_host_ip="127.0.0.1", tftp_board_ip="127.0.0.2",
                                      boot_existing=False, boot=True, capture_seconds=1, output=root / "result")
            # Loopback integration uses 127/8, while production accepts local /24.
            with patch("ram_boot_cli.network_addresses", return_value=("127.0.0.1", "127.0.0.2")), \
                    patch("ram_boot_tftp.network_addresses", return_value=("127.0.0.1", "127.0.0.1")), \
                    patch("ram_boot_cli.prepare", return_value=actual_plan):
                # Keep actual server peer matching the independent curl client.
                def loopback_factory(address, _, files):
                    return factory(address, "127.0.0.1", files)
                thread = threading.Thread(target=peer, daemon=True)
                thread.start()
                try:
                    with redirect_stdout(io.StringIO()):
                        status = run(args, serial, tftp_factory=loopback_factory)
                finally:
                    stop.set()
                    thread.join(timeout=2)
                    os.close(master)
                    os.close(slave)
            self.assertFalse(thread.is_alive())
            if errors:
                raise errors[0]
            passed = mode == "success"
            self.assertEqual(status, 0 if passed else 1)
            metadata = json.loads((root / "result.json").read_text())
            self.assertEqual(metadata["boot_sent"], passed)
            self.assertEqual(metadata["ram_crc_verified"], passed)
            self.assertEqual(metadata["transport"], "tftp")
            self.assertNotIn("saveenv", commands)
            if mode not in ("wrong-ddr", "unknown-setenv", "lost-console", "restore-mismatch"):
                self.assertEqual(settings, original)
                self.assertEqual(metadata["network_restore_status"], "original-network-settings-restored")
            if mode == "wrong-size":
                self.assertFalse(any(command.startswith("crc32") for command in commands))
            if mode == "wrong-ddr":
                self.assertFalse(servers)
                self.assertFalse(any(command.startswith("setenv") for command in commands))
            if mode == "lost-console":
                self.assertIn("console-lost", metadata["network_restore_status"])
                self.assertTrue(commands[-1].startswith("tftp "))
            if passed:
                self.assertEqual(len(metadata["verified_files"]), 2 if external else 1)
                self.assertEqual(len(metadata["tftp_completed_snapshots"]), 2 if external else 1)
                self.assertIn(b"TFTP_PTY_CAPTURE", (root / "result.rx").read_bytes())

    def test_actual_download_crc_restore_then_boot(self):
        self.exercise("success")

    def test_external_rootfs_gets_its_own_size_crc_and_receipt(self):
        self.exercise("success", external=True, autostart="yes")

    def test_external_rootfs_failures_never_boot(self):
        for mode in ("wrong-second-size", "wrong-second-crc"):
            with self.subTest(mode=mode):
                self.exercise(mode, external=True)

    def test_failures_never_boot(self):
        for mode in ("wrong-ddr", "unknown-setenv", "wrong-size", "wrong-crc",
                     "restore-mismatch", "lost-console"):
            with self.subTest(mode=mode):
                self.exercise(mode)


if __name__ == "__main__":
    unittest.main(verbosity=2)
