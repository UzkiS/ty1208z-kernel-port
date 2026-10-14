#!/usr/bin/env python3
"""Wrap an actual combined native rootfs for isolated QEMU; no board packaging."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from check_openwrt_containers import unique
from prepare_openwrt import sha256
from prepare_openwrt_applications import application_variant
from test_openwrt_container_runtime import build_busybox, docker_fixture

PROJECT = Path(__file__).resolve().parents[1]


def prepare(source, taskbase, output):
    if application_variant(source) != "container-qemu":
        raise ValueError("Combined container QEMU wrapper requires its independent source")
    marker = json.loads((source / ".ty1208z-container-qemu-only.json").read_text())
    if marker != {"schema": 1,
                  "scope": "combined native applications and Docker for isolated QEMU only; no board image",
                  "config_sha256": sha256(PROJECT / "openwrt/containers/applications.config")}:
        raise ValueError("Combined container QEMU profile changed")
    work = taskbase / "build/container-applications-qemu"
    work.mkdir(parents=True, exist_ok=True)
    helper, probe = build_busybox(taskbase, work, output)
    native_initrd = unique((source / "bin/targets/hi3798mv100/apps").glob("*rootfs.cpio.gz"),
                           "combined native initrd")
    with tempfile.TemporaryDirectory(prefix="rootfs-", dir=work) as temporary:
        rootfs = Path(temporary) / "root"
        rootfs.mkdir()
        # Use the delivered native archive, rather than a build directory which
        # may have changed since packaging. Device nodes are supplied by our
        # reproducible archive writer without requiring host root privileges.
        subprocess.run([source / "staging_dir/host/bin/cpio", "-id", "--quiet",
                        "--no-absolute-filenames", "--no-preserve-owner",
                        "--nonmatching", "./dev/console", "./dev/null", "dev/console", "dev/null"],
                       input=gzip.decompress(native_initrd.read_bytes()), cwd=rootfs, check=True)
        if (rootfs / "qemu-helper").exists() or (rootfs / "qemu-init").exists():
            raise ValueError("QEMU helper must not exist in the native rootfs")
        fixtures = rootfs / "opt/qemu-container-fixtures"
        fixtures.mkdir(parents=True)
        (rootfs / "qemu-helper").mkdir()
        shutil.copyfile(helper, rootfs / "qemu-helper/busybox")
        (rootfs / "qemu-helper/busybox").chmod(0o755)
        shutil.copyfile(PROJECT / "initramfs/container-applications-qemu-init", rootfs / "qemu-init")
        (rootfs / "qemu-init").chmod(0o755)
        loader = rootfs / "lib/ld-musl-armhf.so.1"
        if not loader.is_symlink() or loader.readlink().as_posix() != "libc.so":
            raise ValueError("Native ARM musl interpreter alias differs")
        libraries = {"lib/libc.so": rootfs / "lib/libc.so",
                     "lib/ld-musl-armhf.so.1": rootfs / "lib/libc.so",
                     "lib/libgcc_s.so.1": rootfs / "lib/libgcc_s.so.1"}
        if any(not path.is_file() or path.is_symlink() for path in libraries.values()):
            raise ValueError("Native tini runtime libraries are absent or indirect")
        docker_fixture(helper, probe, fixtures / "container-image.tar", libraries)
        shutil.copyfile(PROJECT / "tools/openwrt-container-applications-guest.sh", fixtures / "guest.sh")
        shutil.copyfile(probe, fixtures / "container-resource-probe.armhf")
        # Start the actual service explicitly after establishing RAM storage.
        # Leave the original native source/rootfs unchanged.
        service = rootfs / "etc/rc.d/S99dockerd"
        if service.is_symlink():
            service.unlink()
        cpio = work / "combined-rootfs.cpio"
        subprocess.run(["python3", PROJECT / "tools/make_initramfs.py", rootfs, cpio], check=True)
        initrd = output / "container-applications.QEMU-ONLY.cpio.gz"
        initrd.write_bytes(gzip.compress(cpio.read_bytes(), compresslevel=6, mtime=0))
    return initrd, {"qemu_stage": PROJECT / "initramfs/container-applications-qemu-init",
                    "container_guest": PROJECT / "tools/openwrt-container-applications-guest.sh",
                    "container_helper": helper, "container_probe": probe}
