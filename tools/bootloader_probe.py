"""Bounded, read-only inspection of the measured TY1208Z CA bootloader."""
import re
import time


class ProbeError(RuntimeError):
    pass


class BootloaderProbe:
    """Require a fresh identified boot before sending any bytes.

    The only transmitted bytes are one Ctrl+C and these fixed read-only
    commands. No caller-supplied shell text, load/boot, reset or storage commands.
    """

    COMMANDS = (
        b"help\r",
        b"printenv bootcmd bootargs bootdelay loadaddr bootm_low bootm_size\r",
        b"help bootm\r",
        b"help tftp\r",
        b"help loadb\r",
    )
    PROMPT = re.compile(rb"(?:^|[\r\n])fastboot# $")

    def __init__(self, timeout=10):
        self.timeout = timeout
        self.stage = "await-boot-rom"
        self.buffer = b""
        self.deadline = None
        self.completed_commands = 0
        self.sent_commands = 0
        self.interrupt_sent = False

    @property
    def finished(self):
        return self.stage == "complete"

    def snapshot(self):
        return {
            "stage": self.stage, "interrupt_sent": self.interrupt_sent,
            "sent_commands": self.sent_commands,
            "completed_commands": self.completed_commands,
        }

    def check_timeout(self):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise ProbeError(f"Timed out in {self.stage}; no further bytes will be sent")

    def feed(self, data):
        self.check_timeout()
        self.buffer = (self.buffer + data)[-65536:]
        if self.stage == "await-boot-rom":
            marker = self.buffer.find(b"Bootrom start")
            if marker < 0:
                return []
            self.buffer = self.buffer[marker:]
            self.stage = "await-autoboot"
        if (
            self.stage == "await-autoboot" and self.buffer.count(b"Bootrom start") > 1
        ) or (
            self.stage in {"await-prompt", "await-command-prompt"}
            and b"Bootrom start" in self.buffer
        ):
            raise ProbeError("Device restarted during inspection; no further bytes will be sent")
        if self.stage == "await-autoboot":
            # The measured image has bootdelay=0. Queue Ctrl+C while its final
            # reservation table is printing, after board-specific init.
            if b"Reserve Memory" not in self.buffer and b"Press Ctrl+C to stop autoboot" not in self.buffer:
                return []
            if b"Starting kernel ..." in self.buffer:
                raise ProbeError("Autoboot already passed; nothing sent")
            if not (
                b"Fastboot 3.3.0-dirty " in self.buffer
                and re.search(rb"CPU:\s+Hi3798Mv100 \(CA\)[\r\n]", self.buffer)
            ):
                raise ProbeError("Bootloader identity differs from measured CA boot; nothing sent")
            self.interrupt_sent = True
            self.stage = "await-prompt"
            self.buffer = b""
            self.deadline = time.monotonic() + self.timeout
            return [b"\x03"]
        if self.stage in {"await-prompt", "await-command-prompt"}:
            if b"Starting kernel ..." in self.buffer or b" login:" in self.buffer:
                raise ProbeError("Autoboot was not interrupted; no further bytes will be sent")
            if not self.PROMPT.search(self.buffer):
                return []
            if self.stage == "await-command-prompt":
                self.completed_commands += 1
            self.buffer = b""
            if self.sent_commands == len(self.COMMANDS):
                self.stage = "complete"
                self.deadline = None
                return []
            command = self.COMMANDS[self.sent_commands]
            self.sent_commands += 1
            self.stage = "await-command-prompt"
            self.deadline = time.monotonic() + self.timeout
            return [command]
        return []
