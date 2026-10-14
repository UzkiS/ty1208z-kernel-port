#!/usr/bin/env python3
"""Build a private compact first-install image and a RAM-only LuCI backend."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from native_upgrade import digest

PROJECT = Path(__file__).resolve().parents[1]
EPOCH = 1791676800
UUID = "af36aa90-9d68-426c-a070-37f398d71208"


def run(command, *, cwd=None, env=None, log=None):
    subprocess.run([str(x) for x in command], cwd=cwd, env=env,
                   stdout=log, stderr=subprocess.STDOUT if log else None, check=True)


def copy(source, target, mode=0o755):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(mode)


def package(apk, root, output, name, version):
    identity = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            identity.update(os.readlink(path).encode())
        elif path.is_file():
            identity.update(path.read_bytes())
    target = output / (name + "-1.0~" + identity.hexdigest()[:12] + "-r1.apk")
    run([apk, "mkpkg", "--files", root, "--output", target,
         "--info", "name:" + name, "--info", "version:1.0~" + identity.hexdigest()[:12] + "-r1",
         "--info", "arch:arm_cortex-a7_neon-vfpv4", "--info", "license:GPL-2.0-only",
         "--info", "description:TY1208Z compact first installation",
         "--info", "depends:kernel=" + version + " libc"])
    return target


def build_resize(source, work, env):
    archive = source / "dl/e2fsprogs-1.47.3.tar.xz"
    assert digest(archive) == "857e6ef800feaa2bb4578fbc810214be5d3c88b072ea53c5384733a965737329"
    tree = work / "e2fsprogs-1.47.3"
    if not tree.exists():
        with tarfile.open(archive) as packed:
            packed.extractall(work, filter="data")
    main = tree / "resize/main.c"
    original = "\tif (print_min_size)\n\t\topen_flags = O_RDONLY;"
    patched = "\tif (print_min_size || (mount_flags & EXT2_MF_MOUNTED))\n\t\topen_flags = O_RDONLY;"
    text = main.read_text()
    assert text.count(original) == 1 or text.count(patched) == 1, "resize2fs mounted-open anchor differs"
    main.write_text(text.replace(original, patched))
    # Our kernel denies raw writes to mounted devices. Online resize uses an
    # ioctl on the mountpoint; the initial block-device inspection needs only
    # O_RDONLY. Preserve ordinary O_RDWR behavior for offline filesystems.
    # resize2fs uses only libe2p/libext2fs/libcom_err and libc. The configure
    # probes for unrelated UUID/blkid utilities are bypassed; none is linked.
    env = dict(env, ac_cv_lib_uuid_uuid_generate="yes", ac_cv_lib_blkid_blkid_get_cache="yes",
               CFLAGS="-Os", LDFLAGS="-static", BUILD_CC="/usr/bin/gcc")
    with (work / "resize-build.log").open("wb") as log:
        run([tree / "configure", "--host=arm-openwrt-linux-muslgnueabi",
             "--build=x86_64-pc-linux-gnu", "--disable-nls", "--disable-elf-shlibs",
             "--disable-libuuid", "--disable-libblkid", "--disable-fuse2fs",
             "--disable-uuidd", "--disable-mmp", "--disable-e2initrd-helper"], cwd=tree, env=env, log=log)
        for directory in ("lib/et", "lib/ext2fs", "lib/e2p", "resize"):
            if directory == "lib/ext2fs":
                run(["make", "-C", directory, "ext2_err.h"], cwd=tree, env=env, log=log)
            run(["make", "-j8", "-C", directory, *( ["resize2fs"] if directory == "resize" else [])],
                cwd=tree, env=env, log=log)
    binary = tree / "resize/resize2fs"
    run([str(env["STRIP"]), binary])
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--upgraded-root", type=Path, required=True)
    parser.add_argument("--disk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-resize-build", action="store_true")
    args = parser.parse_args()
    assert not args.output.exists() or (args.resume_resize_build and
        not (args.output / "grow").exists()), "Never replace an existing install candidate"
    args.output.mkdir(parents=True, exist_ok=args.resume_resize_build)
    toolchain = args.source / "staging_dir/toolchain-arm-openwrt-linux-muslgnueabi"
    if not toolchain.is_dir():
        candidates = [path for path in (args.source / "staging_dir").glob("toolchain-*")
                      if (path / "bin/arm-openwrt-linux-muslgnueabi-gcc").is_file()]
        assert len(candidates) == 1, "Native ARM toolchain is missing or ambiguous"
        toolchain = candidates[0]
    prefix = toolchain / "bin/arm-openwrt-linux-muslgnueabi-"
    env = dict(os.environ, PATH=str(prefix.parent) + ":" + os.environ["PATH"],
               CC=str(prefix) + "gcc", AR=str(prefix) + "ar", RANLIB=str(prefix) + "ranlib",
               STRIP=str(prefix) + "strip", STAGING_DIR=str(toolchain), SOURCE_DATE_EPOCH=str(EPOCH),
               E2FSPROGS_FAKE_TIME=str(EPOCH))
    apk = args.source / "staging_dir/host/bin/apk"
    fwtool = args.source / "staging_dir/host/bin/fwtool"
    version = (args.upgraded_root / "etc/ty1208z-upgrade-abi").read_text().strip()
    persistent = PROJECT / "openwrt/system/persistent"
    resize = build_resize(args.source, args.output, env)
    grow = args.output / "grow/files"
    copy(resize, grow / "sbin/resize2fs")
    copy(persistent / "grow-root", grow / "etc/init.d/ty1208z-grow-root")
    (grow / "etc/ty1208z-grow-p9").write_text("1GiB -> 6846MiB; fixed p9 only\n")
    (grow / "etc/rc.d").mkdir()
    (grow / "etc/rc.d/S12ty1208z-grow-root").symlink_to("../init.d/ty1208z-grow-root")
    grow_apk = package(apk, grow, args.output, "ty1208z-firstboot-grow", version)
    root = args.output / "root"
    shutil.copytree(args.upgraded_root, root, symlinks=True)
    run([apk, "add", "--root", root, "--usermode", "--arch", "arm_cortex-a7_neon-vfpv4",
         "--allow-untrusted", "--no-network", "--no-scripts", "--no-commit-hooks",
         "--repositories-file", "/dev/null", grow_apk], env=env)
    image = args.output / "rootfs.ext4"
    with image.open("wb") as stream:
        stream.truncate(1073741824)
    run(["fakeroot", "--", "sh", "-c", 'set -eu; chown -hR 0:0 "$1"; shift; exec "$@"',
         "first-install", root, "mke2fs", "-q", "-t", "ext4", "-b", "4096", "-m", "1",
         "-L", "openwrt", "-U", UUID, "-E", "lazy_itable_init=0,lazy_journal_init=0,root_owner=0:0",
         "-d", root, image], env=env)
    run(["e2fsck", "-fn", image])
    packed = args.output / "rootfs.ext4.gz"
    with image.open("rb") as original, packed.open("wb") as output:
        with gzip.GzipFile(filename="", fileobj=output, mode="wb", compresslevel=6, mtime=0) as archive:
            shutil.copyfileobj(original, archive, 1048576)
    kernel = args.disk / "kernel-p6-INSTALL-UNTESTED.bin"
    original = json.loads((args.disk / "manifest.json").read_bytes())
    assert digest(kernel) == original["files"][kernel.name]["sha256"]
    manifest = {"schema": "ty1208z-first-install-v1", "board": "tianyi,ty1208z-ca",
                "layout": "p6-28672-40960_p9-1249280-14020608", "kernel_abi": version,
                "kernel_bytes": kernel.stat().st_size, "kernel_sha256": digest(kernel),
                "root_bytes": packed.stat().st_size, "root_sha256": digest(packed),
                "root_expanded_sha256": digest(image)}
    firmware = args.output / "ty1208z-ca-first-install-UNTESTED.bin"
    data = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    with tarfile.open(firmware, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, path in (("manifest", None), ("kernel", kernel), ("rootfs.ext4.gz", packed)):
            member = tarfile.TarInfo(name)
            member.size = path.stat().st_size if path else len(data)
            member.mode, member.mtime = 0o644, EPOCH
            if path:
                with path.open("rb") as stream:
                    archive.addfile(member, stream)
            else:
                archive.addfile(member, io.BytesIO(data))
    metadata = args.output / "fwtool.json"
    metadata.write_text(json.dumps({"metadata_version": "1.1", "compat_version": "1.0",
                                   "supported_devices": ["tianyi,ty1208z-ca-openwrt-system-ram"],
                                   "version": {"dist": "OpenWrt", "board": "tianyi,ty1208z-ca"}}))
    run([fwtool, "-I", metadata, firmware])
    files = args.output / "installer/files"
    copy(persistent / "first-platform.sh", files / "lib/upgrade/platform.sh")
    copy(persistent / "first-install", files / "sbin/ty1208z-first-install")
    (files / "etc").mkdir()
    (files / "etc/ty1208z-first-installer").write_text(version + "\n")
    for destination, source in (("ty1208z-first-check", "first-image-check.c"),
                                ("emmc-p9-control", "emmc-p9-control.c")):
        run([env["CC"], "-static", "-Os", "-Wall", "-Wextra", "-Werror",
             persistent / source, "-o", files / "sbin" / destination], env=env)
    installer = package(apk, files, args.output, "ty1208z-first-install", version)
    run(["qemu-arm", files / "sbin/ty1208z-first-check", "outer", firmware])
    run(["qemu-arm", files / "sbin/ty1208z-first-check", "kernel", kernel])
    with image.open("rb") as stream:
        subprocess.run(["qemu-arm", str(files / "sbin/ty1208z-first-check"), "ext4"], stdin=stream, check=True)
    receipt = {"status": "private first-install candidate; hardware writing not performed",
               "image": {"file": firmware.name, "bytes": firmware.stat().st_size, "sha256": digest(firmware)},
               "installer": {"file": installer.name, "sha256": digest(installer)},
               "root_bytes_written": 1073741824, "full_p9_bytes": 7178551296,
               "manifest": manifest, "redistribution": "PRIVATE original RDA firmware; do not publish"}
    (args.output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
