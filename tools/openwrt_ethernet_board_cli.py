#!/usr/bin/env python3
"""Capture native RAM networking and start one bounded iperf3 server via UART."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

from board_diag_cli import ShellExchange
from serial_cli import console_text, open_receiver
from ymodem_sender import TransferError

PROMPT = re.compile(rb"(?:^|[\r\n])root@[^\r\n ]+:[^\r\n]*# $")
PROFILES = {
    "net": (b"6.12.112-ty1208z-openwrt-net", b"hi3798mv100/net"),
    "router": (b"6.12.112-ty1208z-openwrt-router", b"hi3798mv100/apps"),
}
REPORT = (
    b"ubus call network.interface.probe status >/tmp/ty1208z-network.json && "
    b"cat /tmp/ty1208z-network.json && "
    b"test \"$(jsonfilter -i /tmp/ty1208z-network.json -e '@.up')\" = true && "
    b"test \"$(jsonfilter -i /tmp/ty1208z-network.json -e '@.proto')\" = dhcp && "
    b"ip address show eth0 && ip route && "
    b"ethtool eth0 && cat /proc/interrupts && cat /proc/net/dev && dmesg && "
    b"time64-probe && test $(cat /sys/class/net/eth0/carrier) = 1 && "
    b"gw=$(ip route | awk '$1==\"default\" {print $3; exit}') && test -n \"$gw\" && "
    b"ping -c 4 -W 2 \"$gw\" && echo OPENWRT_ETHERNET_BOARD_PASS; "
    b"echo TY1208Z_OPENWRT_COMPLETE")
START_IPERF = (
    b"test ! -s /tmp/ty1208z-iperf.pid && "
    b"addr=$(ip -4 address show eth0 | awk '/inet / {split($2,a,\"/\"); print a[1]; exit}') && "
    b"test -n \"$addr\" && "
    b"(iperf3 -s -1 -B \"$addr\" -p 5201 --idle-timeout 60 -J >/tmp/ty1208z-iperf.json 2>&1 & "
    b"echo $! >/tmp/ty1208z-iperf.pid) && sleep 1 && "
    b"kill -0 $(cat /tmp/ty1208z-iperf.pid) && echo OPENWRT_IPERF_READY; "
    b"echo TY1208Z_OPENWRT_COMPLETE")
COLLECT_IPERF = (
    b"test -s /tmp/ty1208z-iperf.json && cat /tmp/ty1208z-iperf.json; "
    b"cat /proc/net/dev; cat /proc/interrupts; "
    b"if test -s /tmp/ty1208z-iperf.pid && ! kill -0 $(cat /tmp/ty1208z-iperf.pid) 2>/dev/null; "
    b"then rm /tmp/ty1208z-iperf.pid; echo OPENWRT_IPERF_FINISHED; fi; "
    b"echo TY1208Z_OPENWRT_COMPLETE")


def command(exchange, data, timeout=12):
    exchange.write(data + b"\r")

    def complete(response):
        if b"fastboot# " in response or b" login:" in response or b"Bootrom start" in response:
            raise TransferError("Not at the native RAM shell; no further commands")
        return PROMPT.search(response)

    report = exchange.until(complete, timeout)
    print(console_text(report.decode("utf-8", "backslashreplace")), end="", flush=True)
    return report


def iperf_summary(report):
    decoder = json.JSONDecoder()
    text = report.decode("utf-8", "backslashreplace")
    for start in re.finditer(r"(?:^|\n)\{", text):
        try:
            data, _ = decoder.raw_decode(text[start.end() - 1:])
        except json.JSONDecodeError:
            continue
        if not data.get("start", {}).get("version", "").startswith("iperf 3.20"):
            continue
        if "error" in data:
            raise TransferError("iperf3 server reported an error")
        end = data.get("end", {})
        summary = {key: end[key] for key in ("sum_sent", "sum_received") if key in end}
        if not summary or not any(item.get("bytes", 0) > 0 for item in summary.values()):
            raise TransferError("iperf3 server recorded no completed data transfer")
        return summary
    raise TransferError("No actual iperf3 3.20 server JSON was captured")


def script_command(exchange, payload):
    # OpenWrt's BusyBox line editor is bounded to 512 bytes. Transfer reviewed
    # fixed scripts in short lines rather than relying on long serial input.
    command(exchange, b"rm -f /tmp/ty1208z-native-test.sh")
    payload += b"\n"
    for offset in range(0, len(payload), 32):
        encoded = ''.join(f"\\0{byte:03o}" for byte in payload[offset:offset+32]).encode()
        command(exchange, b"printf %b '" + encoded + b"' >> /tmp/ty1208z-native-test.sh")
    return command(exchange, b"sh /tmp/ty1208z-native-test.sh", timeout=45)


def run(args, serial_module):
    started = datetime.now(timezone.utc)
    prefix = args.output or Path(__file__).resolve().parents[1] / "evidence" / started.strftime("openwrt-ethernet-%Y%m%dT%H%M%S.%fZ")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {kind: Path(str(prefix) + suffix) for kind, suffix in (
        ("raw", ".rx"), ("journal", ".tx.jsonl"), ("metadata", ".json"))}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Output exists; choose a fresh prefix")
    operation = "iperf-start" if args.iperf_start else "iperf-collect" if args.iperf_collect else "report"
    result = {"schema": 1, "port": args.port, "started_utc": started.isoformat(),
              "profile": args.profile, "operation": operation, "status": "starting", "kernel_verified": False}
    with open_receiver(serial_module, args.port, 115200, 0.02) as port:
        with paths["raw"].open("xb") as raw, paths["journal"].open("x", encoding="utf-8") as journal:
            exchange = ShellExchange(port, raw, journal)
            try:
                command(exchange, b"")
                identity = command(exchange, b"uname -r; cat /etc/openwrt_release")
                release, target = PROFILES[args.profile]
                if (not re.search(rb"(?:^|[\r\n])" + re.escape(release) + rb"[\r\n]", identity) or
                        not re.search(rb"(?:^|[\r\n])DISTRIB_ID='OpenWrt'[\r\n]", identity) or
                        not re.search(rb"(?:^|[\r\n])DISTRIB_TARGET='" + re.escape(target) + rb"'[\r\n]", identity)):
                    raise TransferError("Native kernel/rootfs identity differs; experiment not sent")
                result["kernel_verified"] = True
                data, marker = {
                    "report": (REPORT, b"OPENWRT_ETHERNET_BOARD_PASS"),
                    "iperf-start": (START_IPERF, b"OPENWRT_IPERF_READY"),
                    "iperf-collect": (COLLECT_IPERF, b"OPENWRT_IPERF_FINISHED"),
                }[operation]
                report = script_command(exchange, data)
                if not re.search(rb"(?:^|[\r\n])" + marker + rb"[\r\n]", report):
                    raise TransferError("Operation did not pass; inspect the captured output")
                if operation == "report" and not all(item in report for item in (
                        b"ETH_NET_CLOCK_ENABLED crg51=0000000b inherited-phy",
                        b"ETH_NET_PHY_VERIFIED id=20669823 inherited-no-reset",
                        b"phy_id=0x20669823, phy_mode=mii",
                        b"TIME64_PASS sizeof(time_t)=8")):
                    raise TransferError("Native PHY/driver/time64 acceptance is incomplete")
                if operation == "iperf-collect":
                    result["iperf_summary"] = iperf_summary(report)
                result["status"] = operation + "-passed"
            except (TransferError, OSError, serial_module.SerialException, KeyboardInterrupt) as exc:
                result.update(status="error", error=str(exc) or "Host interrupted")
                print(f"STOP: {result['error']}", file=sys.stderr, flush=True)
            finally:
                result.update(ended_utc=datetime.now(timezone.utc).isoformat(),
                              received_bytes=exchange.rx_bytes, raw_sha256=exchange.digest.hexdigest())
                with paths["metadata"].open("x", encoding="utf-8") as meta:
                    json.dump(result, meta, indent=2)
                    meta.write("\n")
    print(f"Port released; result={result['status']}; raw={paths['raw']}", flush=True)
    return 0 if result["status"].endswith("-passed") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--profile", choices=PROFILES, default="net")
    parser.add_argument("--output", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--iperf-start", action="store_true")
    mode.add_argument("--iperf-collect", action="store_true")
    args = parser.parse_args()
    import serial
    try:
        return run(args, serial)
    except (ValueError, OSError, serial.SerialException) as exc:
        print(f"Native Ethernet UART unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
