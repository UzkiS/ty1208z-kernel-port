"""Real UDP/curl transfers, denial, EOF, retry and peer/deadline boundaries."""
import hashlib
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import unittest

from tftp_readonly import ReadOnlyTftp, TftpError

ALIAS = "ty1208z-uimage.bin"


def rrq(alias=ALIAS, mode="octet", options=()):
    return struct.pack("!H", 1) + b"\0".join(
        [alias.encode(), mode.encode(), *[item.encode() for item in options]]) + b"\0"


class RequestTests(unittest.TestCase):
    def test_request_and_negotiation_boundaries(self):
        name, options = ReadOnlyTftp.request(rrq(options=("blksize", "4096", "tsize", "0")))
        self.assertEqual(name, ALIAS)
        self.assertEqual(ReadOnlyTftp.negotiate(options, 1000),
                         (1468, None, {"blksize": "1468", "tsize": "1000"}))
        self.assertEqual(ReadOnlyTftp.negotiate({"unknown": "value"}, 1000), (512, None, {}))
        for data in (rrq()[:-1], rrq(mode="netascii"), b"\0\2a\0octet\0",
                     rrq(options=("blksize", "512", "BLKSIZE", "1024")),
                     rrq(options=("blksize",)), b"\0\1\xff\0octet\0"):
            with self.subTest(data=data), self.assertRaises(TftpError):
                ReadOnlyTftp.request(data)
        for options in ({"blksize": "7"}, {"blksize": "65465"}, {"blksize": "-1"},
                        {"tsize": "1"}, {"timeout": "0"}, {"timeout": "6"},
                        {"timeout": "1;reboot"}):
            with self.subTest(options=options), self.assertRaises(TftpError):
                ReadOnlyTftp.negotiate(options, 1000)
        with self.assertRaises(TftpError):
            ReadOnlyTftp.negotiate({"blksize": "8"}, 65535 * 8)

    def test_no_paths_empty_images_or_rollover_snapshots(self):
        for alias, data in (("../uImage.bin", b"x"), ("/tmp/image", b"x"),
                            (ALIAS, b""), (ALIAS, b"x" * (512 * 65535))):
            with self.subTest(alias=alias), self.assertRaises(ValueError):
                ReadOnlyTftp("127.0.0.1", "127.0.0.1", [(alias, data)])


class TransferTests(unittest.TestCase):
    def test_real_curl_two_snapshots_options_and_exact_multiple_eof(self):
        if not shutil.which("curl"):
            self.skipTest("curl is required for the independent protocol client")
        self.assertIn("tftp", subprocess.check_output(["curl", "--version"], text=True))
        payloads = [(ALIAS, bytes(range(256)) * 2048),
                    ("ty1208z-initrd.bin", bytes(range(251)) * 7 + b"end")]
        with tempfile.TemporaryDirectory() as directory:
            with ReadOnlyTftp("127.0.0.1", "127.0.0.1", payloads, port=0, timeout=15) as server:
                for index, (alias, data) in enumerate(payloads):
                    output = Path(directory) / f"result-{index}"
                    subprocess.run(["curl", "--silent", "--show-error", "--fail",
                                    "--noproxy", "*", "--max-time", "10", "--tftp-blksize", "1024",
                                    f"tftp://127.0.0.1:{server.port}/{alias}", "--output", str(output)],
                                   check=True, timeout=12)
                    self.assertEqual(output.read_bytes(), data)
                    result = server.wait(alias)
                    self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
                    self.assertEqual(result["block_size"], 1024)
                    self.assertEqual(result["blocks"], len(data) // 1024 + 1)

    def test_wrq_path_and_out_of_order_denied_before_data(self):
        files = [(ALIAS, b"image"), ("ty1208z-initrd.bin", b"rootfs")]
        with ReadOnlyTftp("127.0.0.1", "127.0.0.1", files, port=0) as server:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.bind(("127.0.0.1", 0))
                client.settimeout(1)
                for request in (b"\0\2" + rrq()[2:], rrq("../image"), rrq("ty1208z-initrd.bin")):
                    client.sendto(request, ("127.0.0.1", server.port))
                    packet, peer = client.recvfrom(512)
                    self.assertEqual(peer[1], server.port)
                    self.assertEqual(struct.unpack_from("!HH", packet), (5, 2))
                self.assertFalse(server.completed)
                self.assertIsNone(server.error)

    def test_lost_ack_retries_and_stale_ack_does_not_amplify(self):
        with ReadOnlyTftp("127.0.0.1", "127.0.0.1", [(ALIAS, b"x" * 512)],
                          port=0, retry_seconds=0.15, attempts=3) as server:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.bind(("127.0.0.1", 0))
                client.settimeout(1)
                client.sendto(rrq(), ("127.0.0.1", server.port))
                first, peer = client.recvfrom(2048)
                self.assertEqual(first, b"\0\3\0\1" + b"x" * 512)
                repeated, repeat_peer = client.recvfrom(2048)
                self.assertEqual((repeated, repeat_peer), (first, peer))
                client.sendto(b"\0\4\0\0", peer)
                client.settimeout(0.035)
                with self.assertRaises(socket.timeout):
                    client.recvfrom(2048)
                client.sendto(b"\0\4\0\1", peer)
                client.settimeout(1)
                final, final_peer = client.recvfrom(2048)
                self.assertEqual((final, final_peer), (b"\0\3\0\2", peer))
                client.sendto(b"\0\4\0\2", peer)
                self.assertEqual(server.wait(ALIAS)["bytes"], 512)

    def test_missing_ack_fails_and_never_records_completion(self):
        with ReadOnlyTftp("127.0.0.1", "127.0.0.1", [(ALIAS, b"x")],
                          port=0, retry_seconds=0.025, attempts=2) as server:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.sendto(rrq(), ("127.0.0.1", server.port))
                with self.assertRaisesRegex(TftpError, "retry bound"):
                    server.wait(ALIAS, timeout=1)
                self.assertFalse(server.completed)

    def test_overall_request_deadline_is_bounded(self):
        with ReadOnlyTftp("127.0.0.1", "127.0.0.1", [(ALIAS, b"x")],
                          port=0, timeout=0.1) as server:
            with self.assertRaisesRegex(TftpError, "total time bound"):
                server.wait(ALIAS, timeout=1)

    def test_foreign_peer_is_ignored_and_worker_stops(self):
        started = time.monotonic()
        with ReadOnlyTftp("127.0.0.1", "127.0.0.2", [(ALIAS, b"x")], port=0) as server:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.bind(("127.0.0.1", 0))
                client.settimeout(0.05)
                client.sendto(rrq(), ("127.0.0.1", server.port))
                with self.assertRaises(socket.timeout):
                    client.recvfrom(512)
                self.assertFalse(server.completed)
        self.assertLess(time.monotonic() - started, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
