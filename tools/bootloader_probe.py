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
    ATTACH_COMMANDS = (
        b"help bootm\r", b"help tftp\r", b"help loady\r", b"help loadb\r",
        b"help getinfo\r", b"getinfo ddrfree\r", b"help crc32\r",
        b"printenv bootcmd bootargs bootdelay loadaddr bootm_low bootm_size\r",
        b"printenv ipaddr serverip netmask ethact ethprime autostart\r",
    )
    PROMPT = re.compile(rb"(?:^|[\r\n])fastboot# $")

    def __init__(self, timeout=10, attach=False):
        self.timeout = timeout
        self.attach = attach
        self.stage = "await-existing-prompt" if attach else "await-boot-rom"
        self.buffer = b""
        self.deadline = None
        self.completed_commands = 0
        self.sent_commands = 0
        self.interrupt_sent = False
        self.fresh_marker = b"Bootrom start"

    def start(self):
        # Attach is used only after the user leaves an empty fastboot# prompt.
        # No Ctrl+C, reboot or autoboot interruption is attempted in this mode.
        if self.attach:
            self.deadline = time.monotonic() + self.timeout
            return [b"\r"]
        return []

    @property
    def finished(self):
        return self.stage == "complete"

    def snapshot(self):
        return {
            "stage": self.stage, "interrupt_sent": self.interrupt_sent,
            "attach": self.attach,
            "sent_commands": self.sent_commands,
            "completed_commands": self.completed_commands,
            "fresh_marker": self.fresh_marker.decode("ascii"),
        }

    def check_timeout(self):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise ProbeError(f"Timed out in {self.stage}; no further bytes will be sent")

    def feed(self, data):
        self.check_timeout()
        self.buffer = (self.buffer + data)[-65536:]
        if self.attach:
            if b"Bootrom start" in self.buffer or b"Starting kernel ..." in self.buffer or b" login:" in self.buffer:
                raise ProbeError("Attach is not at a stopped bootloader; no further bytes will be sent")
            if self.stage == "await-existing-prompt":
                if not self.PROMPT.search(self.buffer):
                    return []
                self.stage = "await-version-prompt"
                self.buffer = b""
                self.deadline = time.monotonic() + self.timeout
                return [b"version\r"]
            if self.stage == "await-version-prompt":
                if not self.PROMPT.search(self.buffer):
                    return []
                if not re.search(rb"(?:^|[\r\n])Fastboot 3\.3\.0-dirty ", self.buffer):
                    raise ProbeError("Attached bootloader version differs from measured image; no queries sent")
                self.stage = "await-prompt"
                self.buffer = b"\r\nfastboot# "
        if self.stage == "await-boot-rom":
            if b"Starting kernel ..." in self.buffer or b" login:" in self.buffer:
                raise ProbeError("Fresh boot start was missed; Linux has started; nothing sent")
            marker = self.buffer.find(b"Bootrom start")
            if marker < 0:
                # The first Boot ROM line can be garbled at power-on while the
                # following complete DDR/training/fastboot sequence is intact.
                # Never accept a version, stale prompt or autoboot line alone.
                sequence = re.search(
                    rb"Initializing DDR \.\.\. OK[\r\n]+"
                    rb"Starting DDR training \.\.\. OK[\r\n]+"
                    rb"Starting fastboot \.\.\.", self.buffer)
                if sequence is None:
                    return []
                marker = sequence.start()
                self.fresh_marker = b"Initializing DDR ... OK"
            self.buffer = self.buffer[marker:]
            self.stage = "await-autoboot"
        if (
            self.stage == "await-autoboot" and (
                self.buffer.count(b"Bootrom start") > 1
                or self.buffer.count(b"Initializing DDR ... OK") > 1
            )
        ) or (
            self.stage in {"await-prompt", "await-command-prompt"}
            and (b"Bootrom start" in self.buffer or b"Initializing DDR ... OK" in self.buffer)
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
            commands = self.ATTACH_COMMANDS if self.attach else self.COMMANDS
            if self.sent_commands == len(commands):
                self.stage = "complete"
                self.deadline = None
                return []
            command = commands[self.sent_commands]
            self.sent_commands += 1
            self.stage = "await-command-prompt"
            self.deadline = time.monotonic() + self.timeout
            return [command]
        return []
