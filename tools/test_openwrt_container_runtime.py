#!/usr/bin/env python3
"""Build and run native ARMv7 Docker in QEMU with no NIC, disk or host mounts."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

from check_openwrt_containers import unique
from prepare_openwrt import sha256

PROJECT = Path(__file__).resolve().parents[1]
ROOTS = ("docker", "dockerd", "containerd", "runc", "tini", "kmod-nft-nat")
INPUTS = (
    "tools/test_openwrt_container_runtime.py", "tools/container-resource-probe.c",
    "initramfs/container-qemu-init", "initramfs/container-qemu-guest",
    "config/busybox-container-qemu.fragment", "config/busybox-diagnostic.fragment",
    "config/sources.lock.json", "patches/0002-busybox-stat-time64.patch",
)
MARKERS = (
    "CONTAINER_QEMU_TMPFS_ROOT_SWITCH",
    "CONTAINER_OVERLAY_SECCOMP_NAMESPACE_AND_CGROUP_PASS",
    "CONTAINER_MEMORY_OOM_LIMIT_PASS bytes=33554432",
    "CONTAINER_OVERLAY_LIFECYCLE_CLEANUP_PASS",
    "DOCKER_QEMU_OVERLAY_RUNTIME_PASS",
    "CONTAINER_BRIDGE_EMBEDDED_DNS_HTTP_PASS",
    "CONTAINER_ISOLATED_FORWARD_MASQUERADE_DNAT_PASS",
    "CONTAINER_NETWORK_NAMESPACE_CLEANUP_PASS",
    "DOCKER_QEMU_NETWORK_RUNTIME_PASS",
    "DOCKER_DAEMON_GRACEFUL_SHUTDOWN_PASS",
    "DOCKER_QEMU_RUNTIME_PASS",
)


def package_closure(source):
    apk = source / "staging_dir/host/bin/apk"
    records, providers, selected = {}, {}, {}
    for package in sorted((source / "bin").rglob("*.apk")):
        metadata = json.loads(subprocess.check_output([apk, "adbdump", "--format", "json", package]))
        info = metadata["info"]
        name = info["name"]
        if name in records:
            raise ValueError(f"Ambiguous native APK: {name}")
        records[name] = (package, metadata)
        for provided in [name + "=" + info["version"], *info.get("provides", [])]:
            key, _, version = provided.partition("=")
            providers.setdefault(key, []).append((name, version or info["version"]))

    def select(dependency):
        if dependency.startswith("!"):
            return
        match = re.fullmatch(r"([^<>=~]+)([<>=~].*)?", dependency)
        if match is None:
            raise ValueError(f"Unsupported dependency syntax: {dependency}")
        key, constraint = match.groups()
        candidates = providers.get(key, [])
        if len(candidates) != 1:
            raise ValueError(f"Ambiguous/missing dependency: {dependency}")
        name, version = candidates[0]
        if constraint and constraint != "=" + version:
            raise ValueError(f"Dependency version differs: {dependency}")
        if name in selected:
            return
        package, metadata = records[name]
        info = metadata["info"]
        if info["arch"] not in {"arm_cortex-a7_neon-vfpv4", "all", "noarch"}:
            raise ValueError(f"Wrong native APK architecture: {name}")
        selected[name] = (package, metadata)
        for child in info.get("depends", []):
            select(child)

    for name in ROOTS:
        select(name)
    for name, (_, metadata) in selected.items():
        for dependency in metadata["info"].get("depends", []):
            if dependency.startswith("!") and any(provider in selected for provider, _ in
                                                    providers.get(dependency[1:], [])):
                raise ValueError(f"Conflicting native APK: {name}, {dependency}")
    return apk, selected


def build_busybox(taskbase, work, output):
    lock = json.loads((PROJECT / "config/sources.lock.json").read_text())
    archive = taskbase / "downloads/busybox-1.37.0.tar.bz2"
    if sha256(archive) != lock["busybox"]["sha256"]:
        raise ValueError("BusyBox archive differs from the pinned source")
    source = taskbase / "src/busybox-1.37.0"
    patch = PROJECT / "patches/0002-busybox-stat-time64.patch"
    with patch.open("rb") as stream:
        subprocess.run(["patch", "--dry-run", "--silent", "-R", "--batch", "-p1", "-d", source],
                       stdin=stream, check=True)
    build = work / "busybox"
    build.mkdir(exist_ok=True)
    cross = os.environ.get("CROSS_COMPILE", "arm-linux-gnueabihf-")
    commands = ["make", "-C", str(source), "O=" + str(build), "CROSS_COMPILE=" + cross]
    with (output / "busybox-build.log").open("wb") as log:
        subprocess.run([*commands, "allnoconfig"], check=True, stdout=log, stderr=subprocess.STDOUT)
        for fragment in ("busybox-diagnostic.fragment", "busybox-container-qemu.fragment"):
            subprocess.run(["python3", PROJECT / "tools/merge_fragment.py", build / ".config",
                            PROJECT / "config" / fragment], check=True)
        subprocess.run([*commands, "oldconfig"], input=b"\n" * 8192, check=True,
                       stdout=log, stderr=subprocess.STDOUT)
        subprocess.run([*commands, "silentoldconfig"], check=True, stdout=log, stderr=subprocess.STDOUT)
        subprocess.run([*commands, "-j" + os.environ.get("JOBS", "4")], check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    config = (build / ".config").read_text()
    if 'CONFIG_STATIC=y\n' not in config or 'CONFIG_DEFAULT_MODULES_DIR="/lib/modules"\n' not in config:
        raise ValueError("BusyBox static/module configuration differs")
    payload = output / "busybox.armhf"
    shutil.copyfile(build / "busybox", payload)
    payload.chmod(0o755)
    shutil.copyfile(build / ".config", output / "busybox.config")
    applets = subprocess.check_output(["qemu-arm", payload, "--list"], text=True).splitlines()
    if not {"switch_root", "ip", "modprobe", "depmod", "nslookup", "httpd", "wget",
            "unshare", "nsenter", "pidof"}.issubset(applets):
        raise ValueError("BusyBox lacks the container runtime test applets")
    probe = output / "container-resource-probe.armhf"
    subprocess.run([cross + "gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-static", "-march=armv7-a",
                    "-mfpu=neon", "-mfloat-abi=hard", PROJECT / "tools/container-resource-probe.c",
                    "-o", probe], check=True)
    return payload, probe


def docker_fixture(busybox, probe, destination, native_libraries=None):
    native_libraries = native_libraries or {}
    if native_libraries and set(native_libraries) != {
            "lib/libc.so", "lib/ld-musl-armhf.so.1", "lib/libgcc_s.so.1"}:
        raise ValueError("Native tini fixture requires exactly its ARM musl and libgcc runtime")
    layer = io.BytesIO()
    with tarfile.open(fileobj=layer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in ("bin", "etc", "tmp", "proc", "sys", "dev", *(("lib",) if native_libraries else ())):
            info = tarfile.TarInfo(name)
            info.type, info.mode = tarfile.DIRTYPE, 0o755
            archive.addfile(info)
        for name, payload in (("bin/busybox", busybox), ("bin/resource-probe", probe),
                              *sorted(native_libraries.items())):
            data = payload.read_bytes()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755
            archive.addfile(info, io.BytesIO(data))
        info = tarfile.TarInfo("bin/sh")
        info.type, info.linkname, info.mode = tarfile.SYMTYPE, "busybox", 0o777
        archive.addfile(info)
    data = layer.getvalue()
    config = {"architecture": "arm", "variant": "v7", "os": "linux",
              "config": {"Cmd": ["/bin/sh"], "Env": ["PATH=/bin"]},
              "rootfs": {"type": "layers", "diff_ids": ["sha256:" + hashlib.sha256(data).hexdigest()]},
              "history": [{"created_by": "pinned static ARMv7 fixture; bounded resource probe"}]}
    blob = json.dumps(config, sort_keys=True).encode()
    config_name = hashlib.sha256(blob).hexdigest() + ".json"
    entries = {config_name: blob, "layer/layer.tar": data,
               "manifest.json": json.dumps([{"Config": config_name, "RepoTags": ["ty1208z-busybox:local"],
                                             "Layers": ["layer/layer.tar"]}]).encode()}
    with tarfile.open(destination, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, content in entries.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(content), 0o644
            archive.addfile(info, io.BytesIO(content))


def install_alternatives(rootfs):
    result = {}
    # APK extraction skips install scripts. Apply only the actual nft provider's
    # packaged alternatives; no OpenWrt service/postinstall scripts run on the host.
    for name in ("iptables-nft", "ip6tables-nft"):
        table = rootfs / "lib/apk/packages" / (name + ".alternatives")
        for entry in table.read_text().split():
            priority, relative, target = entry.split(":")
            if (priority != "300" or not re.fullmatch(r"/usr/sbin/(?:ip6?tables)[\w-]*", relative)
                    or target != "xtables-nft-multi"):
                raise ValueError("Unreviewed native nft alternative")
            path = rootfs / relative.lstrip("/")
            if path.exists() or path.is_symlink() or not (path.parent / target).is_file():
                raise ValueError("Native nft alternative collides or lacks its payload")
            path.symlink_to(target)
            result[relative] = target
    return result


def run(taskbase, source):
    os.environ.update(SOURCE_DATE_EPOCH="1791676800", TZ="UTC", LC_ALL="C")
    inputs = {relative: sha256(PROJECT / relative) for relative in INPUTS}
    work = taskbase / "build/container-qemu-runtime"
    output = PROJECT / "artifacts/openwrt-container-qemu"
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").unlink(missing_ok=True)
    native = PROJECT / "artifacts/openwrt-container-packages"
    manifest = json.loads((native / "manifest.json").read_text())
    for filename, expected in manifest["files"].items():
        path = native / filename
        if expected != {"bytes": path.stat().st_size, "sha256": sha256(path)}:
            raise ValueError(f"Native compilation evidence changed: {filename}")
    overlay = json.loads((source / ".ty1208z-overlay.json").read_text())
    for relative, expected in overlay.items():
        if sha256(source / relative) != expected:
            raise ValueError(f"Native compilation input changed: {relative}")
    kernel_dir = unique((source / "build_dir").glob("target-*/linux-hi3798mv100_apps/linux-6.12.112"),
                        "native container dependency kernel")
    if (kernel_dir / ".config").read_bytes() != (native / "linux.config").read_bytes():
        raise ValueError("Runtime kernel configuration differs from native compilation evidence")
    release = (kernel_dir / "include/generated/utsrelease.h").read_text()
    if release != '#define UTS_RELEASE "6.12.112"\n':
        raise ValueError("Runtime kernel release differs from packaged modules")
    apk, packages = package_closure(source)
    for package, _ in packages.values():
        if package.name in manifest["files"] and sha256(package) != manifest["files"][package.name]["sha256"]:
            raise ValueError("Runtime APK differs from native compilation evidence")
    busybox, probe = build_busybox(taskbase, work, output)
    records = {}
    with tempfile.TemporaryDirectory(prefix="rootfs-", dir=work) as temporary:
        rootfs = Path(temporary)
        for name, (package, metadata) in packages.items():
            subprocess.run([apk, "extract", "--allow-untrusted", "--no-chown", "--destination", rootfs, package],
                           check=True, stdout=subprocess.DEVNULL)
            info = metadata["info"]
            records[name] = {key: info[key] for key in ("name", "version", "arch")}
            records[name].update(filename=package.name, sha256=sha256(package), depends=info.get("depends", []))
        alternatives = install_alternatives(rootfs)
        for name in ("bin", "sbin", "dev/pts", "proc", "sys", "tmp", "run", "etc", "opt"):
            (rootfs / name).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(busybox, rootfs / "bin/busybox")
        (rootfs / "bin/busybox").chmod(0o755)
        (rootfs / "bin/sh").symlink_to("busybox")
        for name in ("modprobe", "ip", "depmod"):
            (rootfs / "sbin" / name).symlink_to("/bin/busybox")
        (rootfs / "etc/passwd").write_text("root:x:0:0:root:/root:/bin/sh\n")
        (rootfs / "etc/group").write_text("root:x:0:\n")
        for relative, filename in (("container-qemu-init", "init"), ("container-qemu-guest", "container-init")):
            shutil.copyfile(PROJECT / "initramfs" / relative, rootfs / filename)
            (rootfs / filename).chmod(0o755)
            subprocess.run(["qemu-arm", busybox, "sh", "-n", rootfs / filename], check=True)
        modules = unique((rootfs / "lib/modules").iterdir(), "packaged module release")
        if modules.name != "6.12.112":
            raise ValueError("Module package release differs from runtime kernel")
        subprocess.run(["qemu-arm", busybox, "depmod", "-b", rootfs, modules.name], check=True)
        docker_fixture(busybox, probe, rootfs / "opt/container-image.tar")
        shutil.copyfile(rootfs / "opt/container-image.tar", output / "container-image.tar")
        cpio = work / "rootfs.cpio"
        subprocess.run(["python3", PROJECT / "tools/make_initramfs.py", rootfs, cpio], check=True)
        (output / "rootfs.QEMU-ONLY.cpio.gz").write_bytes(gzip.compress(cpio.read_bytes(), compresslevel=6, mtime=0))
    shutil.copyfile(kernel_dir / "arch/arm/boot/zImage", output / "zImage.QEMU-ONLY")
    shutil.copyfile(kernel_dir / ".config", output / "linux.config")
    shutil.copyfile(source / ".ty1208z-overlay.json", output / "native-overlay.json")
    shutil.copyfile(native / "manifest.json", output / "native-compilation-manifest.json")
    command = ["qemu-system-arm", "-machine", "virt,gic-version=2", "-cpu", "cortex-a7", "-m", "768M",
               "-smp", "1", "-nographic", "-monitor", "none", "-serial", "stdio", "-no-reboot", "-nic", "none",
               "-kernel", str(output / "zImage.QEMU-ONLY"), "-initrd", str(output / "rootfs.QEMU-ONLY.cpio.gz"),
               "-append", "console=ttyAMA0 rdinit=/init ty1208z.qemu_container=1 panic=0"]
    print("DOCKER_QEMU_RUNTIME_START isolated ARMv7; no NIC/disks/host mounts", flush=True)
    with (output / "qemu.log").open("wb") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=420)
    text = (output / "qemu.log").read_text(errors="replace").replace("\r", "")
    if (completed.returncode or any(text.splitlines().count(marker) != 1 for marker in MARKERS)
            or "DOCKER_QEMU_EXPLORATION_FAILED" in text or "Kernel panic" in text):
        raise ValueError("Docker QEMU runtime failed; inspect artifacts/openwrt-container-qemu/qemu.log")
    if inputs != {relative: sha256(PROJECT / relative) for relative in INPUTS}:
        raise ValueError("Container runtime sources changed while the test was running")
    record = {"schema": 1, "status": "QEMU-only ARMv7 Docker runtime passed; physical/final-router untested",
              "scope": {"nic": False, "disks": False, "host_mounts": False, "memory_mib": 768,
                        "future_clock": "2040 guest only", "fw4_passwall_integration": "not tested"},
              "roots": list(ROOTS), "packages": records, "alternatives": alternatives, "markers": list(MARKERS),
              "inputs": inputs, "source_date_epoch": 1791676800,
              "files": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
                        for path in sorted(output.iterdir()) if path.is_file()}}
    (output / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print("DOCKER_QEMU_RUNTIME_PASS ARMv7 overlay2/cgroups/seccomp/DNS/NAT/lifecycle/shutdown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taskbase", type=Path, default=PROJECT / ".work")
    args = parser.parse_args()
    taskbase = args.taskbase.resolve()
    source = unique((taskbase / "container-packages/build").glob("openwrt-*"), "native container source")
    run(taskbase, source)


if __name__ == "__main__":
    main()
