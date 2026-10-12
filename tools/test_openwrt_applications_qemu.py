#!/usr/bin/env python3
"""Exercise the actual ARM application rootfs in isolated QEMU at a 2040 clock."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import selectors
import subprocess
import time


def unique(paths, description):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError(f"Expected exactly one {description}: {paths}")
    return paths[0]


def test(source):
    kernel = unique((source / "build_dir").glob(
        "target-*/linux-hi3798mv100_apps/linux-6.12.112/arch/arm/boot/zImage"), "application kernel")
    images = source / "bin/targets/hi3798mv100/apps"
    initrd = unique(images.glob("*rootfs.cpio.gz"), "application initrd")
    output = images / "checks"
    output.mkdir(exist_ok=True)
    fixture = Path(__file__).with_name("openwrt-applications-guest.sh").read_bytes()
    encoded = base64.b64encode(fixture)
    # BusyBox ash's serial line editor truncates long input lines. Keep each
    # complete command below 256 bytes. The minimal BusyBox has no stty applet.
    commands = [b"printf %s '" + encoded[i:i+192] + b"' >> /tmp/application-test.b64\n"
                for i in range(0, len(encoded), 192)]
    commands.append(b"base64 -d /tmp/application-test.b64 > /tmp/application-test.sh; "
                    b"sh /tmp/application-test.sh\n")
    # No disk, host network, port forwarding or external server is exposed.
    # 512 MiB is an emulation allocation, not a board memory/throughput result.
    process = subprocess.Popen([
        "qemu-system-arm", "-machine", "virt,gic-version=2", "-cpu", "cortex-a7",
        "-m", "512M", "-smp", "1", "-nographic", "-monitor", "none", "-serial", "stdio",
        "-no-reboot", "-nic", "none", "-kernel", str(kernel), "-initrd", str(initrd),
        "-append", "console=ttyAMA0 rdinit=/init panic=0",
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    transcript = bytearray()
    prompt = re.compile(rb"(?:^|[\r\n])root@[^\r\n]*[#$] $")
    consumed = 0
    sent = 0
    activation_at = None
    activations = 0
    deadline = time.monotonic() + 360
    try:
        with (output / "qemu-applications.log").open("wb") as log:
            while time.monotonic() < deadline:
                for key, _ in selector.select(timeout=0.2):
                    data = key.fileobj.read1(65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    transcript.extend(data)
                    log.write(data)
                    log.flush()
                    if activation_at is None and b"Please press Enter" in transcript:
                        activation_at = time.monotonic() + 1
                    if sent < len(commands) and prompt.search(transcript[consumed:]):
                        consumed = len(transcript)
                        process.stdin.write(commands[sent])
                        process.stdin.flush()
                        sent += 1
                if (not sent and activation_at is not None and activations < 3
                        and time.monotonic() >= activation_at):
                    process.stdin.write(b"\r")
                    process.stdin.flush()
                    activations += 1
                    activation_at = time.monotonic() + 2
                if process.poll() is not None:
                    break
            else:
                raise ValueError("Application QEMU timeout; see qemu-applications.log")
        report = bytes(transcript).replace(b"\r", b"")
        markers = (
            b"CERTIFICATE_TIME64_PASS", b"DNS_TIME64_PASS", b"HTTPS_TIME64_PASS",
            b"PASSWALL_LUCI_AUTH_TIME64_PASS",
            b"LUCI_RPCD_TIME64_PASS", b"PASSWALL_XRAY_SOCKS_TIME64_PASS",
            b"NFT_EXPRESSIONS_AND_COUNTER_PASS", b"OPENWRT_APPLICATIONS_QEMU_PASS",
        )
        if (process.returncode != 0 or sent != len(commands)
                or any(b"\n" + marker + b"\n" not in report for marker in markers)
                or b"Kernel panic" in report or b"OPENWRT_APPLICATIONS_QEMU_FAIL" in report
                or not re.search(rb"\nTIME64_PASS sizeof\(time_t\)=8 realtime=22089888[0-9]{2} ", report)):
            raise ValueError("Application QEMU check failed; see qemu-applications.log")
        manifest = unique(images.glob("*.manifest"), "application package manifest")
        artifacts = {}
        for name, path in (("kernel", kernel), ("rootfs", initrd), ("packages", manifest),
                           ("console", output / "qemu-applications.log")):
            with path.open("rb") as source_file:
                artifacts[name] = {"bytes": path.stat().st_size,
                                   "sha256": hashlib.file_digest(source_file, "sha256").hexdigest()}
        provenance = {
            "schema": 1, "result": "OPENWRT_APPLICATIONS_QEMU_PASS",
            "machine": "virt,cortex-a7,single-core", "memory_mib": 512,
            "host_network": False, "disks": False, "clock_year": 2040,
            "artifacts": artifacts, "passed_markers": [marker.decode() for marker in markers],
            "feeds": json.loads((source / ".ty1208z-application-lock.json").read_text()),
            "toolchain": json.loads((source / ".ty1208z-toolchain.json").read_text()),
            "limits": "No MV100 peripherals, hardware routing/TPROXY, performance or Wi-Fi acceptance",
        }
        (output / "applications-qemu.json").write_text(json.dumps(provenance, indent=2) + "\n")
        print("OPENWRT_APPLICATIONS_QEMU_PASS: actual ARM DNS/TLS/LuCI/rpcd/Passwall SOCKS at 2040")
        print("nft counters and TPROXY expressions passed; physical forwarding/TPROXY/Wi-Fi remain untested")
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
    args = parser.parse_args()
    test(args.source)


if __name__ == "__main__":
    main()
