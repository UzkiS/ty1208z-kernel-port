#!/usr/bin/env python3
"""Read fixed diagnostics from the already running RAM-only diag1 shell."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from ram_boot_cli import Exchange
from serial_cli import console_text, open_receiver
from ymodem_sender import TransferError

PROMPT = re.compile(rb"(?:^|[\r\n])(?:/ )?# $")
PROFILES = {
    "diag1": b"6.12.112-ty1208z-diag1",
    "emmc-audit1": b"6.12.112-ty1208z-emmc-audit1",
    "sd-audit1": b"6.12.112-ty1208z-sd-audit1",
    "sd-ident1": b"6.12.112-ty1208z-sd-ident1",
    "sd-ro1": b"6.12.112-ty1208z-sd-ro1",
    "emmc-ident1": b"6.12.112-ty1208z-emmc-ident1",
    "emmc-read1": b"6.12.112-ty1208z-emmc-read1",
    "ethernet-audit1": b"6.12.112-ty1208z-ethernet-audit1",
    "ethernet-clock-id1": b"6.12.112-ty1208z-ethernet-clock-id1",
    "ethernet-net1": b"6.12.112-ty1208z-ethernet-net1",
    "usb-audit1": b"6.12.112-ty1208z-usb-audit1",
    "usb-clock-audit1": b"6.12.112-ty1208z-usb-clock-audit1",
    "usb-host1": b"6.12.112-ty1208z-usb-host1",
    "restart1": b"6.12.112-ty1208z-restart1",
    "ram768": b"6.12.112-ty1208z-ram768",
}


class ShellExchange(Exchange):
    def read(self, size):
        # Shell output has no binary handshake following a prompt. Drain queued
        # bytes together: flushing every byte to a network evidence directory
        # can otherwise overrun the host serial buffer during a dmesg report.
        return super().read(min(max(self.port.in_waiting, size), 4096))


def shell_command(exchange, command, timeout=10):
    exchange.write(command + b"\r")

    def complete(data):
        if b"fastboot# " in data or b" login:" in data or b"Bootrom start" in data:
            raise TransferError("Not at the diagnostic shell; no further commands")
        return PROMPT.search(data)

    response = exchange.until(complete, timeout=timeout)
    print(console_text(response.decode("utf-8", "backslashreplace")), end="", flush=True)
    return response


def run(args, serial_module):
    started = datetime.now(timezone.utc)
    prefix = args.output or Path(__file__).resolve().parents[1] / "evidence" / started.strftime("board-diag-%Y%m%dT%H%M%S.%fZ")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {kind: Path(str(prefix) + suffix) for kind, suffix in (
        ("raw", ".rx"), ("journal", ".tx.jsonl"), ("metadata", ".json"),
    )}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Output already exists; choose a fresh prefix")
    result = {"schema": 1, "started_utc": started.isoformat(), "port": args.port,
              "profile": args.profile,
              "kernel_verified": False, "report_complete": False, "status": "starting"}
    with open_receiver(serial_module, args.port, 115200, 0.02) as port:
        with paths["raw"].open("xb") as raw, paths["journal"].open("x", encoding="utf-8") as journal:
            exchange = ShellExchange(port, raw, journal)
            try:
                shell_command(exchange, b"")
                identity = shell_command(exchange, b"uname -r")
                if not re.search(rb"(?:^|[\r\n])" + re.escape(PROFILES[args.profile]) + rb"[\r\n]", identity):
                    raise TransferError("Kernel identity differs; diagnostic command not sent")
                result["kernel_verified"] = True
                diagnostic = (b"usb-diag; diag" if args.profile == "usb-host1" else
                              b"ram768-diag; diag" if args.profile == "ram768" else
                              b"sd-ro-diag; diag" if args.profile == "sd-ro1" else
                              b"sd-diag; diag" if args.profile == "sd-ident1" else b"diag")
                report = shell_command(exchange, diagnostic + b"; echo TY1208Z_DIAG_COMPLETE",
                                       timeout=120 if args.profile == "ram768" else 30)
                if not re.search(rb"(?:^|[\r\n])TY1208Z_DIAG_COMPLETE[\r\n]", report):
                    raise TransferError("Diagnostic report is incomplete")
                if not re.search(rb"(?:^|[\r\n])TIME64_PASS sizeof\(time_t\)=8 ", report):
                    raise TransferError("Diagnostic time64 probe did not pass")
                if args.profile == "ram768":
                    memory = re.findall(rb"(?:^|[\r\n])RAM768_MEMORY_PASS bytes=536870912 high_pages=(\d+) pfn_min=(\d+) pfn_max=(\d+) memtotal_kib=(\d+) file-removed[\r\n]", report)
                    if (len(memory) != 1 or not 65536 <= int(memory[0][0]) <= 131072 or
                            not 4096 <= int(memory[0][1]) <= int(memory[0][2]) < 196608 or
                            not 700 * 1024 <= int(memory[0][3]) <= 768 * 1024 or
                            b"RAM768_MEMORY_FAILED" in report or
                            b"RAM768_INIT_MEMORY_RETAINED low-16MiB-reservation" not in report or
                            not all(re.search(rb"(?:^|[\r\n])" + marker + rb"[\r\n]", report) for marker in (
                                b"RAM768_PATTERN_PASS pass=0 bytes=536870912",
                                b"RAM768_PATTERN_PASS pass=1 bytes=536870912",
                                b"RAM768_DIAG_COMPLETE file-and-mount-removed"))):
                        raise TransferError("Memory extension stress/PFN/cleanup evidence incomplete")
                    result.update(memory_bytes_verified=536870912, high_pages_verified=int(memory[0][0]),
                                  pfn_min=int(memory[0][1]), pfn_max=int(memory[0][2]),
                                  memtotal_kib=int(memory[0][3]))
                if args.profile == "emmc-audit1" and b"EMMC_AUDIT_READ_ONLY_COMPLETE" not in report:
                    raise TransferError("eMMC register audit did not complete")
                if args.profile == "sd-audit1" and (
                        not all(marker in report for marker in (
                            b"SD_AUDIT CRG39=", b"SD_AUDIT LDO=",
                            b"SD_AUDIT_READ_ONLY_COMPLETE no-card-commands no-control-writes")) or
                        not any(marker in report for marker in (
                            b"SD_AUDIT_CONTROLLER_READ_COMPLETE",
                            b"SD_AUDIT_CONTROLLER_SKIPPED inactive-clock-or-reset"))):
                    raise TransferError("Read-only SD register audit did not complete")
                if args.profile in ("emmc-ident1", "emmc-read1") and not all(marker in report for marker in (
                        b"EMMC_IDENT_GUARD_PASS", b"Using PIO mode.", b"new MMC card",
                        b"name=008G30", b"type=MMC", b"BLOCK_DISABLED",
                        b"EMMC_IDENT_COMPLETE sectors=15269888 bytes=7818182656")):
                    raise TransferError("Restricted eMMC card identification did not complete")
                if args.profile in ("sd-ident1", "sd-ro1"):
                    matched = re.findall(rb"SD_IDENT_COMPLETE bytes=(\d+) clock=(\d+) bus_width=(\d+) timing=(\d+)", report)
                    block_marker = b"BLOCK_DISABLED" if args.profile == "sd-ident1" else b"SD_RO_OVERLAPPING_READ_PASS read_bytes=1024"
                    if (not all(marker in report for marker in (
                            b"SD_IDENT_GUARD_PASS source=50000000 PIO-only", b"Using PIO mode.",
                            b"type=SD", block_marker, b"TY1208Z_MV100_RESTART_READY")) or
                            len(matched) != 1 or not 0 < int(matched[0][0]) <= 2 ** 41 or
                            not 0 < int(matched[0][1]) <= 25000000 or matched[0][2:] != (b"0", b"0") or
                            b"SD_IDENT_NO_CARD" in report):
                        raise TransferError("Restricted SD card identification did not complete")
                    if args.profile == "sd-ro1":
                        blocks = re.findall(rb"(?:^|[\r\n])SD_RO_BLOCK_READ_PASS bytes=(\d+) read_bytes=4096 ro=1[\r\n]", report)
                        complete = re.findall(rb"(?:^|[\r\n])SD_RO_DIAG_COMPLETE filesystems=(\d+) no-card-writes[\r\n]", report)
                        if len(blocks) != 1 or blocks[0] != matched[0][0] or len(complete) != 1:
                            raise TransferError("SD read-only block observation did not complete")
                        mounts = re.findall(rb"(?:^|[\r\n])SD_RO_FS_MOUNT_PASS ro=1 block_size=\d+ blocks=\d+[\r\n]", report)
                        unmounts = re.findall(rb"(?:^|[\r\n])SD_RO_FS_COMPLETE type=(ext4|vfat|exfat) mount-removed no-card-writes[\r\n]", report)
                        if len(mounts) != int(complete[0]) or len(unmounts) != len(mounts):
                            raise TransferError("SD read-only filesystem mount/removal evidence differs")
                        result["read_only_block_verified"] = True
                        result["mounted_filesystems"] = int(complete[0])
                        result["files_read"] = len(re.findall(rb"(?:^|[\r\n])SD_RO_FS_FILE_READ_PASS bytes=[1-9]\d* content-and-name-excluded[\r\n]", report))
                if args.profile == "emmc-read1" and (
                        not all(marker in report for marker in (
                            b"EMMC_SAMPLE_HINAS_HEADER_MATCH crc32=2ba1a125",
                            b"EMMC_SAMPLE_EXT4 magic=ef53",
                            b"EMMC_SAMPLE_READ_COMPLETE count=4 no-block-device"))
                        or b"EMMC_SAMPLE_READ_FAILED" in report):
                    raise TransferError("Fixed read-only eMMC samples did not pass")
                if args.profile == "ethernet-audit1" and not all(marker in report for marker in (
                        b"ETH_AUDIT CRG51=", b"ETH_AUDIT PHY_CRG=", b"ETH_AUDIT PHY_SELECT=",
                        b"ETH_AUDIT PHY_ADDRESS=", b"ETH_AUDIT PHY_LDO=",
                        b"ETH_AUDIT_COMPLETE no-phy-writes no-clock-reset-writes no-dma")):
                    raise TransferError("Inherited Ethernet audit did not complete")
                if args.profile == "ethernet-clock-id1" and (
                        not all(marker in report for marker in (
                            b"ETH_CLOCK_ID_STATE before=00000003 enabled=0000000b restored=00000003 changed=1 verified=1",
                            b"ETH_CLOCK_ID_PHY_ID=",
                            b"ETH_CLOCK_ID_COMPLETE clock-restored no-phy-reset-writes no-dma"))
                        or b"ETH_CLOCK_ID_FAILED" in report):
                    raise TransferError("Temporary Ethernet clock/PHY-ID experiment did not pass")
                if args.profile == "ethernet-net1" and not all(marker in report for marker in (
                        b"ETH_NET_CLOCK_ENABLED crg51=0000000b inherited-phy",
                        b"ETH_NET_PHY_VERIFIED id=20669823 inherited-no-reset",
                        b"phy_id=0x20669823, phy_mode=mii")):
                    raise TransferError("Inherited Ethernet driver/PHY binding did not pass")
                if args.profile == "usb-audit1" and not all(marker in report for marker in (
                        b"USB_AUDIT CRG46=", b"USB_AUDIT USB0=",
                        b"USB_AUDIT_READ_ONLY_COMPLETE no-clock-reset-writes no-device-transactions")):
                    raise TransferError("Read-only USB host0 register audit is incomplete")
                if args.profile == "restart1" and not all(marker in report for marker in (
                        b"TY1208Z_RESTART_OBSERVED pid=", b"cid=b105f00d control=00000000",
                        b"TY1208Z_RESTART_READY no-startup-writes explicit-restart-only")):
                    raise TransferError("SP805 restart identity/registration is incomplete")
                if args.profile == "usb-clock-audit1" and (
                        not all(marker in report for marker in (
                            b"USB_CLOCK_AUDIT_BEFORE CRG46=0013707f CRG47=00000b01 USB0=000c71a8 USB1=00000000 SYSID0=37980100 changed=1",
                            b"USB_CLOCK_AUDIT_CAPS EHCI_CAPBASE=",
                            b"USB_CLOCK_AUDIT_STOP CRG46=0010000e CRG47=00000f03 USB0=000c71a8 USB1=0000a801 error=0",
                            b"USB_CLOCK_AUDIT_COMPLETE sdk-last-user-stop no-device-transactions no-dma no-firmware"))
                        or b"USB_CLOCK_AUDIT_FAILED" in report):
                    raise TransferError("Guarded USB clock/capability experiment did not complete")
                if args.profile == "usb-host1" and (
                        not all(marker in report for marker in (
                            b"USB_HOST0_PREPARED sdk-host0-sequence",
                            b"USB_HOST0_OBSERVATION ehci_root=1 ohci_root=1 rda=",
                            b"USB_HOST0_OBSERVATION_COMPLETE no-class-driver no-firmware-loading"))
                        or not all(re.search(pattern, report) for pattern in (
                            rb"(?:^|[\r\n])f9890000\.usb driver=[^\r\n]+/ehci-platform[\r\n]",
                            rb"(?:^|[\r\n])f9880000\.usb driver=[^\r\n]+/ohci-platform[\r\n]"))
                        or any(marker in report for marker in (
                            b"USB_HOST0_PREPARE_FAILED", b"USB_HOST0_SHUTDOWN_READBACK_FAILED"))):
                    raise TransferError("USB host0 controllers/root hubs did not start completely")
                result["report_complete"] = True
                result["status"] = "diagnostic-captured"
            except (TransferError, OSError, serial_module.SerialException, KeyboardInterrupt) as exc:
                result["status"] = "error"
                result["error"] = str(exc) or "Host interrupted"
                print(f"STOP: {result['error']}", file=sys.stderr, flush=True)
            finally:
                result.update({"ended_utc": datetime.now(timezone.utc).isoformat(),
                               "received_bytes": exchange.rx_bytes, "raw_sha256": exchange.digest.hexdigest()})
                with paths["metadata"].open("x", encoding="utf-8") as meta:
                    json.dump(result, meta, indent=2)
                    meta.write("\n")
    print(f"Port released; result={result['status']}; raw={paths['raw']}", flush=True)
    return 0 if result["report_complete"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--profile", choices=PROFILES, default="diag1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    import serial
    try:
        return run(args, serial)
    except (ValueError, OSError, serial.SerialException) as exc:
        print(f"Board diagnostic unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
