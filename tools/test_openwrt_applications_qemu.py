#!/usr/bin/env python3
"""Exercise the actual ARM application rootfs in isolated QEMU at a 2040 clock."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import time
import zipfile
from prepare_openwrt_applications import application_variant


def unique(paths, description):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError(f"Expected exactly one {description}: {paths}")
    return paths[0]


def identity(path):
    with path.open("rb") as stream:
        return {"bytes": path.stat().st_size,
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def required_markers(variant):
    markers = (
        b"XRAY_UNSYNCHRONIZED_CLOCK_PASS", b"NTP_ERA_TIME64_PASS",
        b"CERTIFICATE_TIME64_PASS", b"DNS_TIME64_PASS", b"HTTPS_TIME64_PASS",
        b"LUCI_CHINESE_DEFAULT_PASS", b"PASSWALL_LUCI_AUTH_TIME64_PASS",
        b"LUCI_RPCD_TIME64_PASS", b"PASSWALL_XRAY_SOCKS_TIME64_PASS",
        b"PASSWALL_XRAY_TLS_TIME64_PASS", b"PASSWALL_SINGBOX_SOCKS_TIME64_PASS",
        b"PASSWALL_SINGBOX_TLS_TIME64_PASS", b"UNZIP_ARCHIVE_TIME64_PASS",
        b"LUCI_EMPTY_ROOT_LOGIN_PASS", b"NFT_EXPRESSIONS_AND_COUNTER_PASS",
        b"OPENWRT_APPLICATIONS_QEMU_PASS",
    )
    if variant in ("ethernet", "ethernet-ram768", "ethernet-sdro", "container-qemu"):
        markers += (b"OPENWRT_ROUTER_FORWARDING_TIME64_PASS", b"PASSWALL_TPROXY_TCP_TIME64_PASS",
                    b"PASSWALL_TPROXY_UDP_TIME64_PASS")
    if variant == "container-qemu":
        markers += (b"CONTAINER_APPLICATIONS_QEMU_NATIVE_TMPFS_ROOT_PASS",
                    b"OPENWRT_DOCKER_PROCD_OVERLAY_CGROUP_PASS", b"OPENWRT_DOCKER_FW4_DNS_NAT_PASS",
                    b"OPENWRT_DOCKER_PASSWALL_XRAY_TPROXY_PASS", b"OPENWRT_DOCKER_PASSWALL_SINGBOX_TPROXY_PASS",
                    b"OPENWRT_DOCKER_AFTER_PASSWALL_FW4_RELOAD_PASS", b"OPENWRT_DOCKER_CLEAN_SHUTDOWN_PASS")
    return markers


def test(source, memory_mib=512, taskbase=None):
    source = source.resolve()
    if taskbase is not None:
        taskbase = taskbase.resolve()
    images = source / "bin/targets/hi3798mv100/apps"
    output = images / "checks"
    suffix = "" if memory_mib == 512 else f"-{memory_mib}"
    provenance_path = output / f"applications-qemu{suffix}.json"
    # Invalidate before profile validation, wrapper preparation or compilation.
    # A failed rerun must not leave a stale successful provenance record.
    provenance_path.unlink(missing_ok=True)
    if (source / ".ty1208z-container-compile-only.json").exists():
        raise ValueError("Compile-only container packages have no application rootfs acceptance")
    variant = application_variant(source)
    combined = variant == "container-qemu"
    ethernet = variant in ("ethernet", "ethernet-ram768", "ethernet-sdro")
    networking = ethernet or combined
    if (combined and memory_mib != 768) or (not combined and memory_mib not in (256, 512)):
        raise ValueError("Application QEMU memory must match its profile: 256/512 MiB, or combined 768 MiB")
    kernel = unique((source / "build_dir").glob(
        "target-*/linux-hi3798mv100_apps/linux-6.12.112/arch/arm/boot/zImage"), "application kernel")
    initrd = unique(images.glob("*rootfs.cpio.gz"), "application initrd")
    output.mkdir(exist_ok=True)
    manifest = unique(images.glob("*.manifest"), "application package manifest")
    ntp_source = Path(__file__).with_name("ntp-qemu-fixture.c")
    test_inputs = {
        "test_harness": Path(__file__),
        "ntp_server_source": ntp_source,
        "ntp_guest": Path(__file__).with_name("openwrt-ntp-guest.sh"),
        "applications_guest": Path(__file__).with_name("openwrt-applications-guest.sh"),
    }
    if networking:
        test_inputs["router_guest"] = Path(__file__).with_name("openwrt-router-guest.sh")
    if combined:
        project = Path(__file__).resolve().parents[1]
        test_inputs.update({name: project / relative for name, relative in (
            ("qemu_wrapper", "tools/prepare_container_applications_qemu.py"),
            ("container_fixture_builder", "tools/test_openwrt_container_runtime.py"),
            ("initramfs_writer", "tools/make_initramfs.py"),
            ("container_configuration", "openwrt/containers/applications.config"),
            ("container_kernel_configuration", "openwrt/containers/applications-kernel.config"),
            ("container_resource_source", "tools/container-resource-probe.c"),
            ("container_helper_configuration", "config/busybox-container-qemu.fragment"),
            ("container_helper_base_configuration", "config/busybox-diagnostic.fragment"),
            ("container_helper_sources", "config/sources.lock.json"),
            ("container_helper_time64_patch", "patches/0002-busybox-stat-time64.patch"),
            ("qemu_stage", "initramfs/container-applications-qemu-init"),
            ("container_guest", "tools/openwrt-container-applications-guest.sh"),
        )})
    native_paths = {
        "kernel": kernel, "rootfs": initrd, "packages": manifest,
        "config": kernel.parents[3] / ".config",
        "feeds": source / ".ty1208z-application-lock.json",
        "toolchain": source / ".ty1208z-toolchain.json",
        "overlay": source / ".ty1208z-overlay.json",
        "openwrt_config": source / ".config",
    }
    if combined:
        native_paths["container_profile"] = source / ".ty1208z-container-qemu-only.json"
    frozen = {path: identity(path) for path in (*native_paths.values(), *test_inputs.values())}
    # Conservatively account for the board's low-16-MiB reservation. virt
    # does not reserve that region, so cap its usable memory for this trial.
    memory_limit_mib = 240 if memory_mib == 256 else memory_mib
    extra_inputs = {}
    native_initrd = initrd
    if combined:
        if taskbase is None:
            raise ValueError("Combined application QEMU requires its explicit pinned build taskbase")
        from prepare_container_applications_qemu import prepare
        initrd, extra_inputs = prepare(source, taskbase, output)
    transcript_path = output / f"qemu-applications{suffix}.log"
    ntp_binary = output / f"ntp-qemu-fixture{suffix}.armhf"
    # Build against the same pinned native ARM/musl toolchain as this rootfs.
    compiler = unique((source / "staging_dir").glob(
        "toolchain-*/bin/arm-openwrt-linux-muslgnueabi-gcc"), "native test compiler")
    subprocess.run([str(compiler), "-std=c11", "-Os", "-Wall", "-Wextra", "-Werror", "-static", "-s",
                    str(ntp_source), "-o", str(ntp_binary)], check=True,
                   env={**os.environ, "STAGING_DIR": str(compiler.parent.parent)})
    fixture = Path(__file__).with_name("openwrt-applications-guest.sh").read_bytes()
    encoded = base64.b64encode(fixture)
    # BusyBox ash's serial line editor truncates long input lines. Keep each
    # complete command below 256 bytes. The minimal BusyBox has no stty applet.
    commands = [b"printf %s '" + encoded[i:i+192] + b"' >> /tmp/application-test.b64\n"
                for i in range(0, len(encoded), 192)]
    # Exercise the delivered InfoZIP binary with stored/deflated data, UTF-8
    # filenames, ZIP64 local headers and a timestamp beyond 2038.
    zip_files = {
        "deflated.txt": b"TY1208Z_UNZIP_2040\n" * 256,
        "stored.bin": bytes(range(256)) * 4,
        "中文目录/中文文件.txt": "中文解压验证\n".encode(),
        "empty.txt": b"",
    }
    zip_files["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in zip_files.items()).encode()
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", allowZip64=True) as archive:
        for name, data in zip_files.items():
            entry = zipfile.ZipInfo(name, date_time=(2040, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_STORED if name == "stored.bin" else zipfile.ZIP_DEFLATED
            with archive.open(entry, "w", force_zip64=True) as output_file:
                output_file.write(data)
    zip_fixture = output / "unzip-fixture.zip"
    zip_fixture.write_bytes(archive_buffer.getvalue())
    encoded_zip = base64.b64encode(zip_fixture.read_bytes())
    commands += [b"printf %s '" + encoded_zip[i:i+192] + b"' >> /tmp/unzip-fixture.b64\n"
                 for i in range(0, len(encoded_zip), 192)]
    commands.append(b"base64 -d /tmp/unzip-fixture.b64 > /tmp/unzip-fixture.zip\n")
    for name, data in (("ntp-fixture", ntp_binary.read_bytes()),
                       ("ntp-test", Path(__file__).with_name("openwrt-ntp-guest.sh").read_bytes())):
        encoded_ntp = base64.b64encode(data)
        commands += [b"printf %s '" + encoded_ntp[i:i+192] + b"' >> /tmp/" + name.encode() + b".b64\n"
                     for i in range(0, len(encoded_ntp), 192)]
    commands += [b"base64 -d /tmp/ntp-fixture.b64 > /tmp/ntp-qemu-fixture; chmod 700 /tmp/ntp-qemu-fixture\n",
                 b"base64 -d /tmp/ntp-test.b64 > /tmp/ntp-runtime-test.sh\n"]
    if networking:
        encoded_router = base64.b64encode(Path(__file__).with_name("openwrt-router-guest.sh").read_bytes())
        commands += [b"printf %s '" + encoded_router[i:i+192] + b"' >> /tmp/router-test.b64\n"
                     for i in range(0, len(encoded_router), 192)]
        commands.append(b"base64 -d /tmp/router-test.b64 > /tmp/router-runtime-test.sh\n")
    commands.append(b"base64 -d /tmp/application-test.b64 > /tmp/application-test.sh; "
                    b"sh /tmp/application-test.sh\n")
    test_inputs.update(ntp_server_binary=ntp_binary, unzip_archive=zip_fixture, **extra_inputs)
    if combined:
        test_inputs["unmodified_native_initrd"] = native_initrd
    artifact_paths = {"kernel": kernel, "rootfs": initrd, "packages": manifest,
                      "config": kernel.parents[3] / ".config"}
    for path in (*artifact_paths.values(), *test_inputs.values()):
        current = identity(path)
        if path in frozen and frozen[path] != current:
            raise ValueError(f"Application QEMU input changed during preparation: {path.name}")
        frozen[path] = current
    # No disk, host network, port forwarding or external server is exposed.
    # Memory size is an emulation allocation, not a board throughput result.
    process = subprocess.Popen([
        "qemu-system-arm", "-machine", "virt,gic-version=2", "-cpu", "cortex-a7",
        "-m", f"{memory_mib}M", "-smp", "1", "-nographic", "-monitor", "none", "-serial", "stdio",
        "-no-reboot", "-nic", "none", "-kernel", str(kernel), "-initrd", str(initrd),
        "-append", (f"console=ttyAMA0 rdinit=/qemu-init ty1208z.qemu_container_apps=1 panic=0 mem={memory_limit_mib}M"
                    if combined else f"console=ttyAMA0 rdinit=/init panic=0 mem={memory_limit_mib}M"),
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    transcript = bytearray()
    prompt = re.compile(rb"(?:^|[\r\n])root@[^\r\n]*[#$] $")
    consumed = 0
    sent = 0
    activation_at = None
    activations = 0
    deadline = time.monotonic() + (720 if combined else 360)
    try:
        with transcript_path.open("wb") as log:
            while time.monotonic() < deadline:
                for key, _ in selector.select(timeout=0.2):
                    data = key.fileobj.read1(65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    transcript.extend(data)
                    log.write(data)
                    log.flush()
                    if b"Initramfs unpacking failed:" in transcript or b"Kernel panic" in transcript:
                        raise ValueError(f"Application QEMU runtime failed; see {transcript_path.name}")
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
                raise ValueError(f"Application QEMU timeout; see {transcript_path.name}")
        report = bytes(transcript).replace(b"\r", b"")
        markers = required_markers(variant)
        if (process.returncode != 0 or sent != len(commands)
                or any(report.splitlines().count(marker) != 1 for marker in markers)
                or b"Kernel panic" in report or b"OPENWRT_APPLICATIONS_QEMU_FAIL" in report
                or not re.search(rb"\nTIME64_PASS sizeof\(time_t\)=8 realtime=22089888[0-9]{2} ", report)):
            raise ValueError(f"Application QEMU check failed; see {transcript_path.name}")
        for path, expected in frozen.items():
            if identity(path) != expected:
                raise ValueError(f"Application QEMU input changed while running: {path.name}")
        artifacts = {name: frozen[path] for name, path in artifact_paths.items()}
        artifacts["console"] = identity(transcript_path)
        provenance = {
            "schema": 1, "result": "OPENWRT_APPLICATIONS_QEMU_PASS",
            "application_variant": variant,
            "machine": "virt,cortex-a7,single-core", "memory_mib": memory_mib,
            "memory_limit_mib": memory_limit_mib,
            "host_network": False, "disks": False, "clock_year": 2040,
            "artifacts": artifacts, "passed_markers": [marker.decode() for marker in markers],
            "test_inputs": {name: frozen[path] for name, path in test_inputs.items()},
            "native_inputs": {name: frozen[path] for name, path in native_paths.items()},
            "feeds": json.loads((source / ".ty1208z-application-lock.json").read_text()),
            "toolchain": json.loads((source / ".ty1208z-toolchain.json").read_text()),
            "limits": "No MV100 peripherals, hardware routing/TPROXY, performance or Wi-Fi acceptance",
        }
        provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
        print("OPENWRT_APPLICATIONS_QEMU_PASS: installed NTP crosses 2036/2038 and sets 2040; ARM DNS/TLS/LuCI/Passwall pass")
        print("nft counters and TPROXY expressions passed; physical forwarding/TPROXY/Wi-Fi remain untested")
        if networking:
            print("Actual netifd/fw4 forwarding and Passwall TCP/UDP TPROXY passed in isolated network namespaces")
        if combined:
            print("Actual procd Docker/overlay2/cgroups/seccomp/fw4/NAT and both container-namespace proxy cores passed")
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
    parser.add_argument("--memory-mib", type=int, choices=(256, 512, 768), default=512)
    parser.add_argument("--taskbase", type=Path)
    args = parser.parse_args()
    test(args.source, args.memory_mib, args.taskbase)


if __name__ == "__main__":
    main()
