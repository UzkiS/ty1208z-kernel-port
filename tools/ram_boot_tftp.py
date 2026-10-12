"""Temporary network setup and measured-address TFTP RAM transfer gates."""
import ipaddress
import re

from tftp_readonly import TftpError
from ymodem_sender import TransferError

VARIABLES = ("autostart", "ipaddr", "serverip", "netmask")
QUERY = "printenv ipaddr serverip netmask autostart"


def network_addresses(host, board):
    host, board = ipaddress.IPv4Address(host), ipaddress.IPv4Address(board)
    network = ipaddress.IPv4Network(f"{host}/24", strict=False)
    if host == board or board not in network:
        raise ValueError("Host and board require different IPv4 addresses in the same /24")
    for address in (host, board):
        if (not address.is_private or address.is_unspecified or address.is_multicast or
                address.is_reserved or address.is_link_local or address.is_loopback or
                address in (network.network_address, network.broadcast_address)):
            raise ValueError("TFTP requires local unicast host and board addresses")
    return str(host), str(board)


def environment(response):
    result = {}
    for name in VARIABLES:
        defined = re.findall(rb"(?:^|[\r\n])" + name.encode() + rb"=([^\r\n]*)[\r\n]", response)
        missing = re.findall(rb'## Error: "' + name.encode() + rb'" not defined', response)
        if len(defined) + len(missing) != 1:
            raise TransferError(f"Ambiguous or missing environment response for {name}")
        try:
            value = defined[0].decode("ascii") if defined else None
        except UnicodeDecodeError as exc:
            raise TransferError(f"Non-ASCII environment response for {name}") from exc
        if value is not None:
            if name == "autostart":
                if value.lower() not in ("yes", "no", "y", "n", "1", "0", "true", "false", "on", "off"):
                    raise TransferError("Unrecognized original autostart value")
            else:
                try:
                    if str(ipaddress.IPv4Address(value)) != value:
                        raise ValueError("Noncanonical IPv4 value")
                except ValueError as exc:
                    raise TransferError(f"Unsafe original network value for {name}") from exc
        result[name] = value
    return result


class TemporaryTftpNetwork:
    def __init__(self, exchange, host, board):
        host, board = network_addresses(host, board)
        self.exchange = exchange
        self.original = None
        self.values = {"autostart": "no", "ipaddr": board,
                       "serverip": host, "netmask": "255.255.255.0"}
        self.active = False
        self.restored = False
        self.restore_status = "not-changed"

    def _set(self, name, value):
        if name not in VARIABLES:
            raise TransferError("Unexpected network variable")
        command = f"setenv {name}" + (f" {value}" if value is not None else "")
        response = self.exchange.command(command)
        if any(marker in response for marker in (b"Unknown command", b"## Error", b"Usage:")):
            raise TransferError(f"Bootloader rejected temporary {name} setting")

    def __enter__(self):
        response = self.exchange.command("help tftp")
        if b"tftp [loadAddress] [bootfilename] <upload_size>" not in response:
            raise TransferError("Live TFTP command differs from recorded bootloader help")
        response = self.exchange.command("help setenv")
        if b"setenv name value" not in response or b"delete environment variable" not in response:
            raise TransferError("Live setenv set/delete syntax is not established")
        self.original = environment(self.exchange.command(QUERY))
        self.active = True
        self.restore_status = "temporary-settings-active"
        try:
            # Prevent an automatic download boot before size/CRC acceptance.
            for name in VARIABLES:
                self._set(name, self.values[name])
            if environment(self.exchange.command(QUERY)) != self.values:
                raise TransferError("Temporary TFTP settings did not read back")
        except BaseException:
            self.restore()
            raise
        return self

    def restore(self):
        if not self.active:
            return
        if not self.exchange.prompt_known:
            self.restore_status = "console-lost; volatile settings require fresh startup"
            return
        # Restore automatic-start policy last, after the transfer has stopped.
        try:
            for name in ("ipaddr", "serverip", "netmask", "autostart"):
                self._set(name, self.original[name])
            if environment(self.exchange.command(QUERY)) != self.original:
                raise TransferError("Original network settings did not read back")
        except BaseException:
            self.restore_status = "restore-failed; volatile settings require fresh startup"
            raise
        self.active = False
        self.restored = True
        self.restore_status = "original-network-settings-restored"

    def __exit__(self, *_):
        self.restore()


def load_snapshot(exchange, server, alias, plan):
    address = plan.get("address", plan.get("header_address"))
    if address not in (0x01FFFFC0, 0x04000000) or alias not in (
            "ty1208z-uimage.bin", "ty1208z-initrd.bin"):
        raise TransferError("TFTP target differs from the bounded RAM plan")
    # No upload-size argument: the measured command's download form.
    exchange.command(f"tftp {address:x} {alias}", timeout=server.timeout)
    try:
        receipt = server.wait(alias)
    except TftpError as exc:
        raise TransferError(f"TFTP download has no completed server receipt: {exc}") from exc
    size = plan.get("bytes", plan.get("image_bytes"))
    digest = plan.get("sha256", plan.get("image_sha256"))
    if receipt["bytes"] != size or receipt["sha256"] != digest:
        raise TransferError("Acknowledged snapshot differs from the planned image")
    response = exchange.command("printenv filesize")
    matches = re.findall(rb"(?:^|[\r\n])filesize=([0-9a-fA-F]{1,8})[\r\n]", response)
    if len(matches) != 1 or int(matches[0], 16) != size:
        raise TransferError("Bootloader TFTP filesize differs; no CRC acceptance or boot")
    return receipt
