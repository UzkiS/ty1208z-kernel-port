#!/usr/bin/env python3
"""Verify/extract pinned OpenWrt and install the independent RAM-only target."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def toolchain_from_native(project, taskbase):
    """Reuse only the completed, fixed native compiler and musl installation."""
    lock = json.loads((project / "openwrt/sources.lock.json").read_text())
    native = taskbase / "build" / ("openwrt-ram-" + lock["openwrt"]["commit"])
    candidates = list((native / "staging_dir").glob("toolchain-arm_cortex-a7+neon-vfpv4_gcc-14.3.0_musl_eabi"))
    if len(candidates) != 1:
        raise ValueError("Build the fixed native OpenWrt toolchain first")
    toolchain = candidates[0]
    if not all((toolchain / "stamp" / name).is_file()
               for name in (".gcc_final_installed", ".musl_installed")):
        raise ValueError("Native compiler/musl build is incomplete")
    compiler = toolchain / "bin/arm-openwrt-linux-muslgnueabi-gcc"
    version = subprocess.check_output([compiler, "-dumpfullversion"], text=True).strip()
    machine = subprocess.check_output([compiler, "-dumpmachine"], text=True).strip()
    if version != "14.3.0" or machine != "arm-openwrt-linux-muslgnueabi":
        raise ValueError("Native toolchain identity differs")
    return toolchain, {"gcc": version, "machine": machine, "compiler_sha256": sha256(compiler),
                       "libc_sha256": sha256(toolchain / "lib/libc.so")}


def extract(archive, destination, root_name):
    # Extract regular files first, then create bounded relative symlinks.
    # Never follow a link from the archive during extraction.
    with tarfile.open(archive) as source:
        members = source.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if not parts or parts[0] != root_name or ".." in parts or Path(member.name).is_absolute():
                raise ValueError(f"Unexpected archive path: {member.name}")
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError(f"Unexpected archive member type: {member.name}")
            if member.issym():
                link = Path(member.linkname)
                target = destination / Path(*parts[1:]).parent / link
                if link.is_absolute() or not target.resolve().is_relative_to(destination.resolve()):
                    raise ValueError(f"Unbounded archive link: {member.name}")
        for member in members:
            if member.issym():
                continue
            relative = Path(*Path(member.name).parts[1:])
            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as data, target.open("xb") as output:
                    shutil.copyfileobj(data, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
        for member in members:
            if member.issym():
                target = destination / Path(*Path(member.name).parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(member.linkname)


def prepare(project, taskbase):
    lock = json.loads((project / "openwrt/sources.lock.json").read_text())
    item = lock["openwrt"]
    if lock["feeds"]:
        raise ValueError("This RAM profile supports the locked core tree only")
    archive = taskbase / "downloads" / item["archive"]
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + ".partial")
        urllib.request.urlretrieve(item["url"], partial)
        if sha256(partial) != item["sha256"]:
            raise ValueError("OpenWrt downloaded archive SHA-256 mismatch")
        partial.replace(archive)
    if sha256(archive) != item["sha256"]:
        raise ValueError("OpenWrt cached archive SHA-256 mismatch")

    destination = taskbase / "build" / ("openwrt-ram-" + item["commit"])
    marker = destination / ".ty1208z-source.json"
    if destination.exists():
        if not marker.exists() or json.loads(marker.read_text()) != item:
            raise ValueError("Unrecognized OpenWrt directory; choose a fresh taskbase")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="openwrt-extract-", dir=destination.parent) as temporary:
            extracted = Path(temporary) / "source"
            extracted.mkdir()
            extract(archive, extracted, "openwrt-" + item["commit"])
            (extracted / marker.name).write_text(json.dumps(item, indent=2) + "\n")
            extracted.rename(destination)

    expected_kernel = (project / "config/sources.lock.json").read_text()
    expected_kernel = json.loads(expected_kernel)["linux"]
    kernel_version = (destination / "target/linux/generic/kernel-6.12").read_text()
    if ("LINUX_VERSION-6.12 = .112\n" not in kernel_version
            or expected_kernel["sha256"] not in kernel_version):
        raise ValueError("OpenWrt kernel differs from the tested board patch base")

    manifest = {}
    for path in sorted((project / "openwrt/overlay").rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project / "openwrt/overlay")
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)
        output.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        manifest[str(relative)] = sha256(path)
    # Reuse the authoritative board patch. Never maintain another copy of the
    # UART/timer drivers here, or copy a standalone kernel module into OpenWrt.
    patch = project / "patches/0001-hi3798mv100-diagnostic.patch"
    relative = Path("target/linux/hi3798mv100/patches-6.12/0001-board-support.patch")
    output = destination / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(patch, output)
    manifest[str(relative)] = sha256(patch)
    busybox_lock = json.loads((project / "config/sources.lock.json").read_text())["busybox"]
    busybox_recipe = (destination / "package/utils/busybox/Makefile").read_text()
    if (f"PKG_VERSION:={busybox_lock['version']}\n" not in busybox_recipe
            or f"PKG_HASH:={busybox_lock['sha256']}\n" not in busybox_recipe):
        raise ValueError("OpenWrt BusyBox differs from the tested time64 patch base")
    relative = Path("package/utils/busybox/patches/900-ty1208z-stat-time64.patch")
    patch = project / "patches/0002-busybox-stat-time64.patch"
    output = destination / relative
    shutil.copyfile(patch, output)
    manifest[str(relative)] = sha256(patch)
    relative = Path("package/ty1208z-time64/src/time64-probe.c")
    probe = project / "tools/time64-probe.c"
    output = destination / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(probe, output)
    manifest[str(relative)] = sha256(probe)
    (destination / "feeds.conf").write_text("# RAM bring-up: no external feeds.\n")
    # codeload archives have no Git revision. OpenWrt's 'unknown' fallback is
    # invalid in the APK package version; preserve the actual fixed commit.
    (destination / "version").write_text("source-" + item["commit"] + "\n")
    from netifd_wireless_eof import apply as fix_netifd_eof
    netifd_file = fix_netifd_eof(destination)
    manifest[str(netifd_file.relative_to(destination))] = sha256(netifd_file)
    (destination / ".ty1208z-overlay.json").write_text(json.dumps(manifest, indent=2) + "\n")
    config = project / "openwrt/config/ram.config"
    if not (destination / ".config").exists():
        shutil.copyfile(config, destination / ".config")
    print(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taskbase", type=Path, required=True)
    args = parser.parse_args()
    prepare(Path(__file__).resolve().parents[1], args.taskbase.resolve())


if __name__ == "__main__":
    main()
