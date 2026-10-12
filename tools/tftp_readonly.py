"""Bounded, single-peer TFTP snapshots for temporary RAM image downloads."""
import hashlib
import ipaddress
import re
import socket
import struct
import threading
import time


class TftpError(RuntimeError):
    pass


class ReadOnlyTftp:
    """Serve only named immutable bytes, in order, to one IPv4 peer.

    No directory, file-write request, dynamic path or persistent service is
    exposed. RFC 1350 octet transfers and blksize/tsize/timeout negotiation
    are supported. Images are bounded to avoid 16-bit block-number rollover.
    """

    def __init__(self, address, peer, files, *, port=69, timeout=300,
                 retry_seconds=1, attempts=5):
        self.address = str(ipaddress.IPv4Address(address))
        self.peer = str(ipaddress.IPv4Address(peer))
        self.files = tuple((name, bytes(data)) for name, data in files)
        if (not self.files or len(self.files) > 2 or
                len({name for name, _ in self.files}) != len(self.files)):
            raise ValueError("One or two distinct RAM snapshots are required")
        for name, data in self.files:
            if not re.fullmatch(r"ty1208z-[a-z0-9-]+\.bin", name):
                raise ValueError("TFTP alias is not a fixed RAM-image name")
            if not 0 < len(data) < 512 * 65535:
                raise ValueError("Snapshot exceeds the no-rollover transfer bound")
        if (not 0 <= port <= 65535 or not 0 < timeout <= 600 or
                not 0 < retry_seconds <= 5 or not 1 <= attempts <= 10):
            raise ValueError("Invalid bounded TFTP timing or port")
        self.port = port
        self.timeout = timeout
        self.retry_seconds = retry_seconds
        self.attempts = attempts
        self.completed = []
        self.error = None
        self._stop = threading.Event()
        self._changed = threading.Condition()
        self._thread = None
        self._listener = None
        self._deadline = None

    @staticmethod
    def _error_packet(code, message):
        return struct.pack("!HH", 5, code) + message.encode("ascii") + b"\0"

    @staticmethod
    def request(data):
        if len(data) > 512 or len(data) < 4 or not data.endswith(b"\0"):
            raise TftpError("Malformed TFTP request")
        opcode = struct.unpack_from("!H", data)[0]
        if opcode != 1:
            raise TftpError("Only read requests are supported")
        try:
            fields = [value.decode("ascii") for value in data[2:-1].split(b"\0")]
        except UnicodeDecodeError as exc:
            raise TftpError("Non-ASCII TFTP request") from exc
        if len(fields) < 2 or fields[1].lower() != "octet" or (len(fields) - 2) % 2:
            raise TftpError("Only complete octet requests are supported")
        options = {}
        for index in range(2, len(fields), 2):
            key, value = fields[index].lower(), fields[index + 1]
            if not key or key in options or not value:
                raise TftpError("Empty or duplicate TFTP option")
            options[key] = value
        return fields[0], options

    @staticmethod
    def negotiate(options, length):
        block_size, interval = 512, None
        accepted = {}
        for name, value in options.items():
            if name not in ("blksize", "tsize", "timeout"):
                continue
            if not re.fullmatch(r"[0-9]{1,8}", value):
                raise TftpError("Invalid numeric TFTP option")
            number = int(value)
            if name == "blksize":
                if not 8 <= number <= 65464:
                    raise TftpError("Invalid block size")
                block_size = min(number, 1468)
                accepted[name] = str(block_size)
            elif name == "tsize":
                if number:
                    raise TftpError("Read request tsize must be zero")
                accepted[name] = str(length)
            else:
                if not 1 <= number <= 5:
                    raise TftpError("Requested timeout exceeds retry bound")
                interval = number
                accepted[name] = value
        if length // block_size + 1 > 65535:
            raise TftpError("Requested block size would require rollover")
        return block_size, interval, accepted

    def __enter__(self):
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._listener.bind((self.address, self.port))
            self.port = self._listener.getsockname()[1]
            self._listener.settimeout(0.1)
            self._deadline = time.monotonic() + self.timeout
            self._thread = threading.Thread(target=self._serve, name="ram-tftp", daemon=True)
            self._thread.start()
        except BaseException:
            self._listener.close()
            self._listener = None
            raise
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                raise TftpError("TFTP worker did not stop within its bound")
        if self._listener is not None:
            self._listener.close()

    def _remaining(self):
        if self._stop.is_set():
            raise TftpError("TFTP server stopped")
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TftpError("TFTP session exceeded its total time bound")
        return remaining

    def _acknowledged(self, transfer, peer, packet, block, interval):
        for _ in range(self.attempts):
            self._remaining()
            transfer.sendto(packet, peer)
            deadline = min(self._deadline, time.monotonic() + interval)
            while time.monotonic() < deadline:
                self._remaining()
                transfer.settimeout(min(0.1, max(deadline - time.monotonic(), 0.001)))
                try:
                    reply, source = transfer.recvfrom(512)
                except socket.timeout:
                    continue
                if source != peer:
                    continue
                if len(reply) >= 2 and struct.unpack_from("!H", reply)[0] == 5:
                    raise TftpError("TFTP client returned an error")
                if len(reply) != 4:
                    continue
                opcode, received = struct.unpack("!HH", reply)
                if opcode == 4 and received == block:
                    return
                # Duplicate/stale ACKs do not extend a deadline or amplify data.
        raise TftpError("TFTP acknowledgement retry bound exceeded")

    def _transfer(self, peer, data, options):
        block_size, interval, accepted = self.negotiate(options, len(data))
        interval = self.retry_seconds if interval is None else interval
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as transfer:
            transfer.bind((self.address, 0))
            if accepted:
                oack = struct.pack("!H", 6) + b"".join(
                    key.encode() + b"\0" + value.encode() + b"\0"
                    for key, value in accepted.items())
                self._acknowledged(transfer, peer, oack, 0, interval)
            for block, offset in enumerate(range(0, len(data) + 1, block_size), 1):
                payload = data[offset:offset + block_size]
                packet = struct.pack("!HH", 3, block) + payload
                self._acknowledged(transfer, peer, packet, block, interval)
                if len(payload) < block_size:
                    break
        return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "block_size": block_size, "blocks": len(data) // block_size + 1}

    def _serve(self):
        try:
            rejected = 0
            for expected, data in self.files:
                while True:
                    self._remaining()
                    try:
                        request, peer = self._listener.recvfrom(513)
                    except socket.timeout:
                        continue
                    if peer[0] != self.peer:
                        continue
                    try:
                        name, options = self.request(request)
                        if name != expected:
                            raise TftpError("Requested alias is not the next RAM image")
                        self.negotiate(options, len(data))
                    except TftpError:
                        self._listener.sendto(self._error_packet(2, "RAM snapshot request denied"), peer)
                        rejected += 1
                        if rejected >= 8:
                            raise TftpError("TFTP rejected-request bound exceeded")
                        continue
                    result = self._transfer(peer, data, options)
                    with self._changed:
                        self.completed.append({"alias": name, **result})
                        self._changed.notify_all()
                    break
        except (OSError, TftpError) as exc:
            with self._changed:
                self.error = str(exc)
                self._changed.notify_all()

    def wait(self, alias, timeout=5):
        deadline = time.monotonic() + timeout
        with self._changed:
            while True:
                for result in self.completed:
                    if result["alias"] == alias:
                        return dict(result)
                if self.error is not None:
                    raise TftpError(self.error)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TftpError("TFTP completion record is missing")
                self._changed.wait(remaining)
