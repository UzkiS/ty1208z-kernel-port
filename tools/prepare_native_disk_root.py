#!/usr/bin/env python3
"""Stage a disk root and p6 kernel, optionally building the full p9 image."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from inspect_images import parse_fdt

ROOT = Path(__file__).resolve().parents[1]
PARTITIONS = {
    "p6": {"offset_bytes": 14 * 1024**2, "bytes": 20 * 1024**2},
    "p9": {"offset_bytes": 610 * 1024**2, "bytes": 6846 * 1024**2},
}


def digest(path):
    with path.open("rb") as handle:
        return {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(handle, "sha256").hexdigest()}


def build_full_p9(tree, output, environment, uuid):
    image = output / "rootfs-p9.ext4"
    with image.open("wb") as handle:
        handle.truncate(PARTITIONS["p9"]["bytes"])
    script = 'set -eu; chown -hR 0:0 "$1"; shift; exec "$@"'
    command = ["fakeroot", "--", "sh", "-c", script, "disk-root", str(tree),
               "mke2fs", "-q", "-t", "ext4", "-b", "4096", "-m", "1", "-L", "openwrt",
               "-U", uuid, "-E", "lazy_itable_init=0,lazy_journal_init=0,root_owner=0:0",
               "-d", str(tree), str(image)]
    with (output / "filesystem-build.log").open("wb") as log:
        subprocess.run(command, check=True, env=environment, stdout=log, stderr=subprocess.STDOUT)
        subprocess.run(["e2fsck", "-fn", str(image)], check=True, stdout=log, stderr=subprocess.STDOUT)
    compressed = image.with_suffix(".ext4.gz")
    with image.open("rb") as source, compressed.open("wb") as target:
        with gzip.GzipFile(filename="", fileobj=target, mode="wb", compresslevel=1, mtime=0) as archive:
            shutil.copyfileobj(source, archive, length=1024 * 1024)
    return {p.name: digest(p) for p in (image, compressed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-build", type=Path, required=True)
    parser.add_argument("--package-work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-full-p9", action="store_true",
                        help="Stage root/kernel for compact first-install and sysupgrade without a 6846 MiB image")
    args = parser.parse_args()
    for command in ("fakeroot", "mke2fs", "e2fsck", "cpp", "dtc", "mkimage"):
        assert shutil.which(command), "Missing disk preparation tool: " + command
    kernel = args.kernel_build / "linux-6.12.112"
    state = json.loads((args.kernel_build / "kernel-build.json").read_bytes())
    assert state["persistent_candidate"] and state["exit_code"] == 0
    assert state["status"] == "integrated-native-kernel-built-not-booted"
    assert "CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE=y\n" in (kernel / ".config").read_text()
    assert not args.output.exists(), "Inspect existing disk delivery before replacing it"
    args.output.mkdir(parents=True)
    tree = args.output / "root"
    shutil.copytree(args.package_work / "native-package-supplement/root", tree, symlinks=True)
    firmware = args.package_work / "root/lib/firmware"
    shutil.copytree(firmware, tree / "lib/firmware", dirs_exist_ok=True, symlinks=True)
    defaults = tree / "etc/uci-defaults/98-ty1208z-docker-network"
    shutil.copyfile(ROOT / "openwrt/system/docker-network", defaults)
    defaults.chmod(0o755)
    assert (tree / "lib/preinit/79-ty1208z-disk-root").is_file()
    assert (tree / "usr/bin/xray").is_file() and (tree / "usr/bin/sing-box").is_file()
    assert not (tree / "etc/ty1208z-system-bootstrap").exists()
    # The kernel boots /sbin/init directly with no initrd. The unused RAM init
    # belongs to base-files, so retain its package-owned file in the disk tree.
    uuid = "af36aa90-9d68-426c-a070-37f398d71208"
    environment = dict(os.environ, E2FSPROGS_FAKE_TIME="1791676800", SOURCE_DATE_EPOCH="1791676800")
    files = {} if args.skip_full_p9 else build_full_p9(tree, args.output, environment, uuid)
    dts = args.output / "disk-root.dts"
    dtb = args.output / "disk-root.dtb"
    subprocess.run(["cpp", "-nostdinc", "-undef", "-x", "assembler-with-cpp",
                    "-I", str(ROOT / "overlay/arch/arm/boot/dts/hisilicon"),
                    "-I", str(kernel / "include"), str(ROOT / "openwrt/system/persistent/disk-root.dts"),
                    str(dts)], check=True)
    subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb), str(dts)], check=True)
    props = {n["path"]: n["properties"] for n in parse_fdt(dtb.read_bytes())["nodes"]}
    assert "linux,initrd-start" not in props["/chosen"]
    assert "root=/dev/mmcblk0p9" in props["/chosen"]["bootargs"]["strings"][0]
    payload = args.output / "zImage-dtb"
    payload.write_bytes((kernel / "arch/arm/boot/zImage").read_bytes() + dtb.read_bytes())
    uimage = args.output / "kernel-p6-INSTALL-UNTESTED.bin"
    subprocess.run(["mkimage", "-A", "arm", "-O", "linux", "-T", "kernel", "-C", "none",
                    "-a", "0x02000000", "-e", "0x02000000", "-n", "TY1208Z disk root UNTESTED",
                    "-d", str(payload), str(uimage)], check=True, env=environment)
    assert uimage.stat().st_size < PARTITIONS["p6"]["bytes"]
    files.update({p.name: digest(p) for p in (uimage, dtb)})
    receipt = {"schema": 1, "status": "private offline disk candidate; not booted or authorized for writing",
               "kernel_build": digest(args.kernel_build / "kernel-build.json"), "files": files,
               "partitions": PARTITIONS, "filesystem": "ext4 full p9; direct writable root; Docker /opt/docker",
               "filesystem_uuid": uuid, "full_p9_image_built": not args.skip_full_p9,
               "root_password": "empty default", "hardware_actions": False,
               "persistent_writes": False, "redistribution": "RDA5995 firmware published with project-owner authorization; see firmware/rda5995/manifest.json",
               "required_before_install": ["accepted cold-loader memory/boot layout", "specific p6/p9 write authorization",
                                          "limited physical write/readback", "disk-root boot and persistence acceptance"]}
    (args.output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "files": files}))


if __name__ == "__main__":
    main()
