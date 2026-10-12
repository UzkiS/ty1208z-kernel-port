#!/usr/bin/env python3
"""Exercise YMODEM framing/handshake/retry against a real Linux PTY peer."""
import binascii
import os
import select
import sys
import threading
import time
import unittest

import serial

from ymodem_sender import ACK, CAN, CRC, EOT, NAK, SOH, STX, TransferError, YmodemSender


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration runs on Linux")
class YmodemTests(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = os.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        self.port = serial.Serial(os.ttyname(self.slave), 115200, timeout=0.01, write_timeout=1)
        self.addCleanup(self.port.close)

    def read_exact(self, size):
        data = bytearray()
        deadline = time.monotonic() + 5
        while len(data) < size and time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.05)[0]:
                data.extend(os.read(self.master, size - len(data)))
        self.assertEqual(len(data), size, "Incomplete frame at PTY receiver")
        return bytes(data)

    def receive_packet(self, number, size):
        frame = self.read_exact(size + 5)
        self.assertEqual(frame[:3], bytes((SOH if size == 128 else STX, number & 255, (number & 255) ^ 255)))
        payload = frame[3:-2]
        self.assertEqual(int.from_bytes(frame[-2:], "big"), binascii.crc_hqx(payload, 0))
        return payload

    def run_transfer(self, data, double_eot=False, retry=False):
        received = bytearray()
        errors = []

        def receiver():
            try:
                os.write(self.master, bytes((CRC,)))
                header = self.receive_packet(0, 128)
                filename, size = header.split(b"\0", 2)[:2]
                self.assertEqual(filename, b"ty1208z-diag1.bin")
                self.assertEqual(int(size), len(data))
                os.write(self.master, bytes((ACK, CRC)))
                for index, offset in enumerate(range(0, len(data), 1024), 1):
                    block = self.receive_packet(index, 1024)
                    if retry and index == 2:
                        os.write(self.master, bytes((CRC,)))
                        self.assertEqual(self.receive_packet(index, 1024), block)
                    received.extend(block[:min(1024, len(data) - offset)])
                    os.write(self.master, bytes((ACK,)))
                self.assertEqual(self.read_exact(1), bytes((EOT,)))
                if double_eot:
                    os.write(self.master, bytes((NAK,)))
                    self.assertEqual(self.read_exact(1), bytes((EOT,)))
                os.write(self.master, bytes((ACK, CRC)))
                self.assertEqual(self.receive_packet(0, 128), b"\0" * 128)
                os.write(self.master, bytes((ACK,)))
            except BaseException as exc:
                errors.append(exc)
                os.write(self.master, bytes((CAN,)))

        thread = threading.Thread(target=receiver, daemon=True)
        thread.start()
        try:
            YmodemSender(self.port, timeout=2).send(data)
        finally:
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "PTY receiver did not finish")
        if errors:
            raise errors[0]
        self.assertEqual(bytes(received), data)

    def test_length_padding_and_sequence_wrap(self):
        self.run_transfer(bytes(range(256)) * 1024 + b"tail\x1a")

    def test_standard_two_eot_handshake(self):
        self.run_transfer(b"short data", double_eot=True)

    def test_receiver_crc_mode_retry(self):
        self.run_transfer(b"retry" * 500, retry=True)

    def test_receiver_cancel_stops_before_file(self):
        os.write(self.master, bytes((CAN,)))
        with self.assertRaisesRegex(TransferError, "cancelled"):
            YmodemSender(self.port, timeout=0.2).send(b"data")
        self.assertFalse(select.select([self.master], [], [], 0.05)[0])

    def test_timeout_does_not_send_unsolicited_file(self):
        with self.assertRaisesRegex(TransferError, "timeout"):
            YmodemSender(self.port, timeout=0.1).send(b"data")
        self.assertFalse(select.select([self.master], [], [], 0.05)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
