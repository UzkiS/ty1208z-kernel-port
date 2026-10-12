#!/usr/bin/env python3
"""Boot actual native OpenWrt RAM userspace on QEMU virt, no disk or network."""
import argparse
from pathlib import Path
import re
import selectors
import subprocess
import time


def test(source, subtarget="ram"):
    kernels = list((source / "build_dir").glob(f"target-*/linux-hi3798mv100_{subtarget}/zImage-initramfs"))
    if len(kernels) != 1:
        raise ValueError("Expected one actual OpenWrt initramfs kernel")
    output = source / f"bin/targets/hi3798mv100/{subtarget}/checks"
    output.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([
        "qemu-system-arm", "-machine", "virt,gic-version=2", "-cpu", "cortex-a7",
        "-m", "256M", "-smp", "1", "-nographic", "-monitor", "none", "-serial", "stdio",
        "-no-reboot", "-nic", "none", "-kernel", str(kernels[0]),
        "-append", "console=ttyAMA0 rdinit=/init panic=0",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    transcript = bytearray()
    activation_at = None
    activation_count = 0
    sent = False
    consumed = 0
    command_index = 0
    deadline = time.monotonic() + 90
    # This future wall-clock change happens only in the isolated QEMU process.
    # Validate procd/ubus, UCI and logging as well as the installed musl probe.
    command = (
        b"n=0; while [ ! -S /dev/log ] && [ $n -lt 30 ]; "
        b"do n=$((n+1)); sleep 1; done; test -S /dev/log && "
        b"time64-probe --set-clock-2040 && "
        b"test $(date -u +%Y) = 2040 && "
        b"touch /tmp/time64-stat && test $(stat -c %Y /tmp/time64-stat) -ge 2208988800 && "
        b"uci -q get network.loopback.proto && "
        b"ubus call system board && "
        b"logger -t time64 OPENWRT_LOG_2040 && sleep 1 && "
        b"logread -e OPENWRT_LOG_2040 && echo OPENWRT_RAM_QEMU_PASS "
        b"|| echo OPENWRT_RAM_QEMU_FAIL; poweroff\n"
    )
    if subtarget == "net":
        # Loopback exercise verifies the actual native traffic tools without
        # suggesting that QEMU tested the MV100 Ethernet controller.
        command = command.replace(b"time64-probe --set-clock-2040 && ", (
            b"time64-probe --set-clock-2040 && "
            b"(iperf3 -s -1 -B 127.0.0.1 -p 5201 -J >/tmp/iperf-server.json 2>&1 & "
            b"server=$!; sleep 1; iperf3 -c 127.0.0.1 -p 5201 -t 2 -J >/tmp/iperf-client.json && "
            b"wait $server && grep -q '\"bytes\"' /tmp/iperf-client.json && "
            b"echo OPENWRT_ETHERNET_TOOLS_PASS) && "))
    # The plain native BusyBox has printf but no base64 applet. Octal chunks
    # avoid extra tools, shell interpolation and serial line truncation.
    commands = [b"printf %b '" + ''.join(f"\\0{byte:03o}" for byte in command[offset:offset+32]).encode() +
                b"' >> /tmp/native-test.sh\n" for offset in range(0, len(command), 32)]
    commands.append(b"sh /tmp/native-test.sh\n")
    try:
        with (output / "qemu-native.log").open("wb") as log:
            while time.monotonic() < deadline:
                for key, _ in selector.select(timeout=0.5):
                    data = key.fileobj.read1(65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    transcript.extend(data)
                    log.write(data)
                    log.flush()
                    if activation_at is None and activation_count < 3 and b"Please press Enter" in transcript:
                        # askfirst configures/flushed its TTY after printing
                        # the prompt. Send Enter once the console is ready.
                        activation_at = time.monotonic() + 1
                    if not sent and re.search(rb"(?:^|[\r\n])root@[^\r\n]*[#$] $", transcript[consumed:]):
                        activation_count = 3
                        consumed = len(transcript)
                        process.stdin.write(commands[command_index])
                        process.stdin.flush()
                        command_index += 1
                        sent = command_index == len(commands)
                if (not sent and activation_at is not None and activation_count < 3
                        and time.monotonic() >= activation_at):
                    process.stdin.write(b"\r")
                    process.stdin.flush()
                    activation_count += 1
                    activation_at = time.monotonic() + 2
                if process.poll() is not None:
                    break
            else:
                raise ValueError("Native OpenWrt QEMU timeout; see qemu-native.log")
        report = bytes(transcript).replace(b"\r", b"")
        if (process.returncode != 0 or not sent
                or not re.search(rb"\nOPENWRT_RAM_QEMU_PASS\n", report)
                or not re.search(rb"\nTIME64_PASS sizeof\(time_t\)=8 realtime=22089888[0-9]{2} ", report)
                or not re.search(rb"\nstatic\n", report)
                or b'"kernel": "6.12.112' not in report
                or not re.search(rb"\n[^\n]*2040[^\n]*time64[^\n]*OPENWRT_LOG_2040\n", report)
                or b"Kernel panic" in report or b"TIME64_FAIL" in report):
            raise ValueError("Native OpenWrt QEMU check failed; see qemu-native.log")
        if subtarget == "net" and not re.search(rb"\nOPENWRT_ETHERNET_TOOLS_PASS\n", report):
            raise ValueError("Native Ethernet tools did not pass the loopback check")
        print("OPENWRT_RAM_QEMU_PASS: native musl, procd/ubus, UCI, logging and 2040 timestamps")
        print("No MV100 hardware, Ethernet, Wi-Fi or Passwall operation was tested")
    finally:
        selector.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--subtarget", choices=("ram", "net"), default="ram")
    args = parser.parse_args()
    test(args.source, args.subtarget)


if __name__ == "__main__":
    main()
