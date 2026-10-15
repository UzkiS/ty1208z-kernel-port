#!/usr/bin/env python3
"""Own the board upgrade APK and bounded file-level sysupgrade image format."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile

PROJECT = Path(__file__).resolve().parents[1]
MANAGED = ("bin", "etc", "init", "lib", "sbin", "usr", "var", "www")
BOARD = "tianyi,ty1208z-ca"
SCHEMA = "ty1208z-file-upgrade-v1"
EPOCH = 1791676800
FILES = {
    "lib/upgrade/platform.sh": "platform.sh",
    "sbin/ty1208z-upgrade": "ty1208z-upgrade",
    "etc/init.d/ty1208z-upgrade-cleanup": "upgrade-cleanup",
}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_identity():
    sources = [PROJECT / "openwrt/system/upgrade" / name for name in FILES.values()]
    sources += [PROJECT / "openwrt/system/upgrade/image-check.c",
                PROJECT / "openwrt/system/persistent/emmc-p9-control.c", Path(__file__)]
    return {p.relative_to(PROJECT).as_posix(): digest(p) for p in sources}


def make_package(compiler, apk, version, output):
    """Build a separately installable real APK, bound to the exact kernel ABI."""
    output.mkdir(parents=True)
    root = output / "files"
    root.mkdir()
    for name, source in FILES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / "openwrt/system/upgrade" / source, target)
        target.chmod(0o644 if target.suffix in (".json", ".js") else 0o755)
    for destination, source in {
        "ty1208z-image-check": "upgrade/image-check.c",
        "emmc-p9-control": "persistent/emmc-p9-control.c",
    }.items():
        subprocess.run([str(compiler), "-static", "-s", "-Os", "-Wall", "-Wextra", "-Werror",
                        str(PROJECT / "openwrt/system" / source), "-o", str(root / "sbin" / destination)],
                       check=True, env=dict(os.environ, STAGING_DIR=str(compiler.parent.parent.parent)))
    (root / "etc/ty1208z-upgrade-abi").write_text(version + "\n")
    (root / "etc/rc.d").mkdir(parents=True)
    (root / "etc/rc.d/S98ty1208z-upgrade-cleanup").symlink_to("../init.d/ty1208z-upgrade-cleanup")
    identity = hashlib.sha256(json.dumps(source_identity(), sort_keys=True).encode()).hexdigest()[:12]
    package = output / ("ty1208z-upgrade-1.0~" + identity + "-r1.apk")
    subprocess.run([str(apk), "mkpkg", "--files", str(root), "--output", str(package),
                    "--info", "name:ty1208z-upgrade", "--info", "version:1.0~" + identity + "-r1",
                    "--info", "arch:arm_cortex-a7_neon-vfpv4", "--info", "license:GPL-2.0-only",
                    "--info", "description:TY1208Z web firmware upgrades preserving Docker data",
                    "--info", "depends:kernel=" + version + " libc"], check=True,
                   env=dict(os.environ, SOURCE_DATE_EPOCH=str(EPOCH)))
    return package


def root_archive(root, output):
    """Only firmware paths, never Docker/user data, hardlinks or device nodes."""
    space = 0
    with output.open("wb") as target:
        with gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0, compresslevel=6) as packed:
            with tarfile.open(fileobj=packed, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
                for top in MANAGED:
                    first = root / top
                    if not first.exists() and not first.is_symlink():
                        raise ValueError("Missing managed root entry: " + top)
                    paths = [first]
                    if first.is_dir() and not first.is_symlink():
                        paths += sorted(first.rglob("*"))
                    for path in paths:
                        name = path.relative_to(root).as_posix()
                        mode = path.lstat().st_mode
                        member = tarfile.TarInfo(name)
                        member.mode = stat.S_IMODE(mode)
                        member.mtime, member.uid, member.gid = EPOCH, 0, 0
                        if stat.S_ISLNK(mode):
                            member.type, member.linkname = tarfile.SYMTYPE, os.readlink(path)
                        elif stat.S_ISDIR(mode):
                            member.type = tarfile.DIRTYPE
                        elif stat.S_ISREG(mode):
                            member.size = path.stat().st_size
                        else:
                            raise ValueError("Unsupported upgrade file: " + name)
                        space += ((member.size + 4095) & ~4095) + 8192
                        if member.isfile():
                            with path.open("rb") as payload:
                                archive.addfile(member, payload)
                        else:
                            archive.addfile(member)
    return space


def make_image(root, kernel, version, fwtool, output):
    rootfs = output / "rootfs.tar.gz"
    space = root_archive(root, rootfs)
    manifest = {"schema": SCHEMA, "board": BOARD,
                "layout": "p6-28672-40960_p9-1249280-14020608",
                "kernel_bytes": kernel.stat().st_size, "kernel_sha256": digest(kernel),
                "root_bytes": rootfs.stat().st_size, "root_sha256": digest(rootfs),
                "root_space": space, "kernel_abi": version}
    image = output / "ty1208z-ca-sysupgrade-UNTESTED.bin"
    data = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    with tarfile.open(image, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, source in (("manifest", io.BytesIO(data)), ("kernel", kernel), ("rootfs.tar.gz", rootfs)):
            member = tarfile.TarInfo(name)
            member.size = len(data) if name == "manifest" else source.stat().st_size
            member.mode, member.mtime = 0o644, EPOCH
            if isinstance(source, Path):
                with source.open("rb") as payload:
                    archive.addfile(member, payload)
            else:
                archive.addfile(member, source)
    metadata = output / "fwtool.json"
    metadata.write_text(json.dumps({"metadata_version": "1.1", "compat_version": "1.0",
                                  "supported_devices": ["tianyi,ty1208z-ca-openwrt-system-ram"],
                                  "version": {"dist": "OpenWrt", "board": BOARD}}) + "\n")
    subprocess.run([str(fwtool), "-I", str(metadata), str(image)], check=True)
    return image, manifest
