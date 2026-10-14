#!/usr/bin/env python3
"""Explicitly restart only the identified SP805 RAM experiment and inspect its next boot."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

from board_diag_cli import ShellExchange, shell_command
from bootloader_probe import BootloaderProbe, ProbeError
from serial_cli import console_text, open_receiver
from ymodem_sender import TransferError
from openwrt_ethernet_board_cli import command as native_command, DT_IDENTITY, SOURCE_REVISION

SD_DT_IDENTITY = b"cat /sys/firmware/devicetree/base/compatible; echo"
SD_RO_RESTART_GUARD = (b"if grep -q '^/dev/mmcblk0' /proc/mounts; then echo SD_RO_MOUNT_ACTIVE; "
                       b"else if test -e /sys/class/block/mmcblk0; then test "
                       b'"$(cat /sys/class/block/mmcblk0/ro)" = 1; else test ! -e /sys/class/block/mmcblk0; fi && echo SD_RO_RESTART_GUARD; fi')
RAM768_RESTART_GUARD = (b"if grep -q ' /tmp/ram768-area ' /proc/mounts; then echo RAM768_MOUNT_ACTIVE; "
                       b"else test ! -e /tmp/ram768-area/memory-test && echo RAM768_RESTART_GUARD; fi")
EMMC_RO_RESTART_GUARD = (b"if grep -q '^/dev/mmcblk0' /proc/mounts || "
                         b"grep -Eq '^[^ ]+ [^ ]+ 179:' /proc/self/mountinfo || "
                         b"test -e /tmp/emmc-ro-mount; then echo EMMC_RO_MOUNT_ACTIVE; "
                         b"else test -e /sys/class/block/mmcblk0 && "
                         b'test "$(cat /sys/class/block/mmcblk0/ro)" = 1 && '
                         b'test "$(cat /sys/class/block/mmcblk0/size)" = 15269888 && '
                         b"echo EMMC_RO_RESTART_GUARD; fi")


def run(args, serial_module):
    started = datetime.now(timezone.utc)
    prefix = args.output or Path(__file__).resolve().parents[1] / "evidence" / started.strftime("board-restart-%Y%m%dT%H%M%S.%fZ")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {key: Path(str(prefix) + suffix) for key, suffix in (
        ("raw", ".rx"), ("journal", ".tx.jsonl"), ("metadata", ".json"))}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Output exists; choose a fresh prefix")
    result = {"schema": 1, "port": args.port, "started_utc": started.isoformat(),
              "status": "starting", "kernel_verified": False, "restart_sent": False,
              "persistent_writes": False}
    profile = getattr(args, "profile", "diagnostic")
    native = profile in ("router", "router768", "router-sdro", "router-emmcro")
    sd_ident = profile in ("sd-ident1", "sd-ro1")
    sd_shutdown = sd_ident or profile == "router-sdro"
    memory = profile == "ram768"
    emmc_ro = profile in ("emmc-ro1", "router-emmcro")
    result["profile"] = profile
    command = native_command if native else shell_command
    probe = BootloaderProbe()
    with open_receiver(serial_module, args.port, 115200, 0.01) as port:
        with paths["raw"].open("xb") as raw, paths["journal"].open("x", encoding="utf-8") as journal:
            exchange = ShellExchange(port, raw, journal)
            try:
                command(exchange, b"")
                identity = command(exchange, b"uname -r")
                release = (rb"6\.12\.112" if native else re.escape(("6.12.112-ty1208z-" + profile).encode()) if sd_ident or memory or emmc_ro
                           else rb"6\.12\.112-ty1208z-restart1")
                if not re.search(rb"(?:^|[\r\n])" + release + rb"[\r\n]", identity):
                    raise TransferError("Not the SP805 RAM experiment; no restart sent")
                if native:
                    system = command(exchange, b"cat /etc/openwrt_release")
                    board = (b"tianyi,ty1208z-ca-openwrt-emmcro-ram" if profile == "router-emmcro" else
                             b"tianyi,ty1208z-ca-openwrt-sdro-ram" if profile == "router-sdro" else
                             b"tianyi,ty1208z-ca-openwrt-router768-ram" if profile == "router768" else
                             b"tianyi,ty1208z-ca-openwrt-router-ram")
                    if (b"DISTRIB_TARGET='hi3798mv100/apps'" not in system or
                            b"DISTRIB_REVISION='" + SOURCE_REVISION + b"'" not in system or
                            not re.search(rb"(?:^|[\r\n])" + re.escape(board) + rb"[\r\n]",
                                          command(exchange, DT_IDENTITY))):
                        raise TransferError("Native router source/DT differs; no restart sent")
                    if profile != "router-emmcro":
                        binding = command(exchange, b"test -e /sys/module/ty1208z_sp805_restart && "
                                          b"readlink /sys/bus/platform/devices/ty1208z-sp805-restart/driver")
                        if b"../../../bus/platform/drivers/ty1208z-sp805-restart" not in binding:
                            raise TransferError("Actual RAM restart module binding missing")
                    if profile == "router-sdro":
                        state = command(exchange, SD_RO_RESTART_GUARD)
                        if not re.search(rb"(?:^|[\r\n])SD_RO_RESTART_GUARD[\r\n]", state):
                            raise TransferError("Native SD read-only guard or unmounted state missing; no restart sent")
                        state = command(exchange, RAM768_RESTART_GUARD)
                        if not re.search(rb"(?:^|[\r\n])RAM768_RESTART_GUARD[\r\n]", state):
                            raise TransferError("Native SD memory test cleanup missing; no restart sent")
                if sd_ident:
                    board = b"sd-ro" if profile == "sd-ro1" else b"sd-ident"
                    if not re.search(rb"(?:^|[\r\n])tianyi,ty1208z-ca-" + board + rb"-ram\x00hi3798mv100-series\x00",
                                     command(exchange, SD_DT_IDENTITY)):
                        raise TransferError("SD identification DT differs; no restart sent")
                    binding = command(exchange, b"readlink /sys/bus/platform/devices/f8a2c000.sd-restart/driver")
                    if b"../../../bus/platform/drivers/ty1208z-mv100-sd-restart" not in binding:
                        raise TransferError("Actual SD-profile restart binding missing")
                    if profile == "sd-ro1":
                        state = command(exchange, SD_RO_RESTART_GUARD)
                        if not re.search(rb"(?:^|[\r\n])SD_RO_RESTART_GUARD[\r\n]", state):
                            raise TransferError("SD read-only guard or unmounted state missing; no restart sent")
                if emmc_ro:
                    board = (b"tianyi,ty1208z-ca-openwrt-emmcro-ram" if native else b"tianyi,ty1208z-ca-emmc-ro-ram")
                    if not re.search(rb"(?:^|[\r\n])" + re.escape(board) + rb"\x00hi3798mv100-series\x00",
                                     command(exchange, SD_DT_IDENTITY)):
                        raise TransferError("eMMC read-only DT differs; no restart sent")
                    binding = command(exchange, b"readlink /sys/bus/platform/devices/f8a2c000.emmc-ro-restart/driver")
                    if b"../../../bus/platform/drivers/ty1208z-mv100-emmc-ro-restart" not in binding:
                        raise TransferError("Actual eMMC RO restart binding missing")
                    if not re.search(rb"(?:^|[\r\n])EMMC_RO_RESTART_GUARD[\r\n]",
                                     command(exchange, EMMC_RO_RESTART_GUARD)):
                        raise TransferError("eMMC RO unmounted/capacity/cleanup guard missing; no restart sent")
                if memory:
                    if b"tianyi,ty1208z-ca-ram768\x00hi3798mv100-series\x00" not in command(exchange, SD_DT_IDENTITY):
                        raise TransferError("Memory experiment DT differs; no restart sent")
                    binding = command(exchange, b"readlink /sys/bus/platform/devices/f8a2c000.ram-restart/driver")
                    if b"../../../bus/platform/drivers/ty1208z-mv100-ram-restart" not in binding:
                        raise TransferError("Memory experiment restart binding missing")
                    if not re.search(rb"(?:^|[\r\n])RAM768_RESTART_GUARD[\r\n]",
                                     command(exchange, RAM768_RESTART_GUARD)):
                        raise TransferError("Memory test file/mount still active; no restart sent")
                result["kernel_verified"] = True
                report = command(exchange, b"dmesg; echo TY1208Z_RESTART_CHECK_COMPLETE")
                if (not re.search(rb"(?:^|[\r\n])[^\r\n]*TY1208Z_RESTART_READY "
                                  rb"no-startup-writes explicit-restart-only[\r\n]", report) or
                        not re.search(rb"(?:^|[\r\n])TY1208Z_RESTART_CHECK_COMPLETE[\r\n]", report)):
                    raise TransferError("Actual restart registration missing; no restart sent")
                if (native or sd_ident or memory or emmc_ro) and b"TY1208Z_MV100_RESTART_READY sysid=37980100 measured-inactive-watchdog no-startup-writes" not in report:
                    raise TransferError("Measured MV100 restart guard missing")
                # PID 1 is the diagnostic shell, not an init service manager.
                # This fixed -f command enters the kernel restart syscall.
                exchange.write(b"reboot\r" if native else b"reboot -f\r")
                result["restart_sent"] = True
                result["status"] = "restart-sent"
                deadline = time.monotonic() + args.timeout
                failure_tail = b""
                while not probe.finished:
                    if time.monotonic() >= deadline:
                        raise TransferError("No completed fresh bootloader inspection after restart")
                    probe.check_timeout()
                    data = exchange.read(min(max(port.in_waiting, 1), 4096))
                    if not data:
                        continue
                    print(console_text(data.decode("utf-8", "backslashreplace")), end="", flush=True)
                    failure_tail = (failure_tail + data)[-4096:]
                    if sd_shutdown and b"SD_IDENT_SHUTDOWN_COMPLETE host-removed clock-disabled no-card-writes" in failure_tail:
                        result["sd_shutdown_verified"] = True
                    if emmc_ro and b"EMMC_RO_SHUTDOWN_COMPLETE host-removed clock-disabled no-card-writes" in failure_tail:
                        result["emmc_shutdown_verified"] = True
                    if any(marker in failure_tail for marker in (
                            b"TY1208Z_RESTART_REFUSED", b"TY1208Z_RESTART_TIMEOUT", b"Reboot failed",
                            b"SD_IDENT_SHUTDOWN_FAILED", b"EMMC_RO_SHUTDOWN_FAILED", b"EMMC_RO_RESTART_REFUSED")):
                        raise TransferError("Kernel restart failed; no retry")
                    for outgoing in probe.feed(data):
                        exchange.write(outgoing)
                if sd_shutdown and not result.get("sd_shutdown_verified"):
                    raise TransferError("SD shutdown completion missing from actual restart stream")
                if emmc_ro and not result.get("emmc_shutdown_verified"):
                    raise TransferError("eMMC shutdown completion missing from actual restart stream")
                result["status"] = "restart-bootloader-verified"
            except (TransferError, ProbeError, OSError, serial_module.SerialException, KeyboardInterrupt) as exc:
                result.update(status="error", error=str(exc) or "Host interrupted")
                print(f"STOP: {result['error']}", file=sys.stderr, flush=True)
            finally:
                result.update(ended_utc=datetime.now(timezone.utc).isoformat(),
                              received_bytes=exchange.rx_bytes, raw_sha256=exchange.digest.hexdigest(),
                              probe=probe.snapshot())
                with paths["metadata"].open("x", encoding="utf-8") as metadata:
                    json.dump(result, metadata, indent=2)
                    metadata.write("\n")
    print(f"Port released; result={result['status']}; raw={paths['raw']}", flush=True)
    return 0 if result["status"] == "restart-bootloader-verified" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", choices=("diagnostic", "router", "router768", "router-sdro", "router-emmcro", "sd-ident1", "sd-ro1", "emmc-ro1", "ram768"), default="diagnostic")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    if not 5 <= args.timeout <= 120:
        parser.error("timeout must be 5..120 seconds")
    import serial
    try:
        return run(args, serial)
    except (OSError, ValueError, serial.SerialException) as exc:
        print(f"Restart UART unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
