"""Bounded single-file YMODEM-CRC sender; no device commands or boot policy."""
import binascii
import time

SOH, STX, EOT, ACK, NAK, CAN, CRC = 1, 2, 4, 6, 21, 24, 67


class TransferError(RuntimeError):
    pass


def packet(number, payload, size):
    if size not in (128, 1024) or len(payload) > size:
        raise ValueError("Invalid YMODEM payload size")
    payload = payload.ljust(size, b"\x1a")
    return (bytes((SOH if size == 128 else STX, number & 255, (number & 255) ^ 255))
            + payload + binascii.crc_hqx(payload, 0).to_bytes(2, "big"))


class YmodemSender:
    def __init__(self, channel, timeout=5, retries=5, progress=lambda done, total: None):
        self.channel = channel
        self.timeout = timeout
        self.retries = retries
        self.progress = progress

    def control(self, accepted):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            data = self.channel.read(1)
            if not data:
                continue
            value = data[0]
            if value == CAN:
                raise TransferError("Receiver cancelled YMODEM")
            if value in accepted:
                return value
            # ASCII console text is tolerated only when awaiting the first C
            # (the caller already consumed the loady READY announcement).
            if accepted != {CRC}:
                raise TransferError(f"Unexpected YMODEM response: 0x{value:02x}")
        raise TransferError("YMODEM response timeout")

    def block(self, frame):
        for attempt in range(self.retries):
            self.channel.write(frame)
            try:
                # U-Boot xyzModem requests a retry with C in CRC mode.
                response = self.control({ACK, NAK, CRC})
            except TransferError as exc:
                if "timeout" not in str(exc) or attempt == self.retries - 1:
                    raise
                continue
            if response == ACK:
                return
        raise TransferError("YMODEM block retry limit reached")

    def send(self, data, filename="ty1208z-diag1.bin"):
        if not data or len(filename.encode("ascii")) > 80 or "/" in filename or "\\" in filename or "\0" in filename:
            raise ValueError("Invalid single-file YMODEM input")
        self.control({CRC})
        header = filename.encode("ascii") + b"\0" + str(len(data)).encode("ascii") + b"\0"
        self.block(packet(0, header.ljust(128, b"\0"), 128))
        self.control({CRC})
        for index, offset in enumerate(range(0, len(data), 1024), start=1):
            self.block(packet(index, data[offset:offset + 1024], 1024))
            self.progress(min(offset + 1024, len(data)), len(data))
        # Accept U-Boot's ACK on the first EOT and the common NAK/EOT/ACK form.
        self.channel.write(bytes((EOT,)))
        response = self.control({ACK, NAK})
        if response == NAK:
            self.channel.write(bytes((EOT,)))
            if self.control({ACK, NAK}) != ACK:
                raise TransferError("Receiver rejected the final EOT")
        self.control({CRC})
        self.block(packet(0, b"\0" * 128, 128))
