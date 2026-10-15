#!/usr/bin/env python3
"""Prepare a new private web-upgrade delivery; never open a hardware device."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from native_upgrade import digest, make_image, make_package, source_identity
from prepare_openwrt import toolchain_from_native
from prepare_native_package_supplement import public_runtime_metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taskbase", type=Path, required=True)
    parser.add_argument("--disk-root", type=Path, required=True,
                        help="Existing accepted private delivery, including root and kernel")
    parser.add_argument("--source", type=Path, required=True, help="Native source with host apk/fwtool")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Inspect existing delivery; never overwrite it"
    args.output.mkdir(parents=True)
    project = Path(__file__).resolve().parents[1]
    toolchain, toolchain_identity = toolchain_from_native(project, args.taskbase)
    apk = args.source / "staging_dir/host/bin/apk"
    fwtool = args.source / "staging_dir/host/bin/fwtool"
    old_root = args.disk_root / "root"
    rows = (old_root / "lib/apk/db/installed").read_text().split("\n\n")
    kernel_rows = [row for row in rows if "P:kernel\n" in row + "\n"]
    assert len(kernel_rows) == 1
    version = next(line[2:] for line in kernel_rows[0].splitlines() if line.startswith("V:"))
    compiler = toolchain / "bin/arm-openwrt-linux-muslgnueabi-gcc"
    package = make_package(compiler, apk, version, args.output / "package")
    root = args.output / "root"
    shutil.copytree(old_root, root, symlinks=True)
    environment = dict(os.environ, SOURCE_DATE_EPOCH="1791676800")
    with (args.output / "apk-install.log").open("wb") as log:
        subprocess.run([str(apk), "add", "--root", str(root), "--usermode",
                        "--arch", "arm_cortex-a7_neon-vfpv4", "--allow-untrusted", "--no-network",
                        "--no-scripts", "--no-commit-hooks", "--repositories-file", "/dev/null", str(package)],
                       check=True, stdout=log, stderr=subprocess.STDOUT, env=environment)
    for name in ("usr/bin/xray", "usr/bin/sing-box", "bin/busybox", "lib/modules/6.12.112/rdawfmac.ko",
                 "etc/config/network", "etc/shadow"):
        assert (root / name).read_bytes() == (old_root / name).read_bytes(), name
    public_runtime_metadata(root)
    kernel = args.disk_root / "kernel-p6-INSTALL-UNTESTED.bin"
    original = json.loads((args.disk_root / "manifest.json").read_bytes())
    assert digest(kernel) == original["files"][kernel.name]["sha256"]
    image, manifest = make_image(root, kernel, version, fwtool, args.output)
    checker = root / "sbin/ty1208z-image-check"
    subprocess.run(["qemu-arm", str(checker), "outer", str(image)], check=True)
    subprocess.run(["qemu-arm", str(checker), "kernel", str(kernel)], check=True)
    receipt = {"status": "public offline web upgrade candidate; physical acceptance pending",
               "image": {"file": image.name, "bytes": image.stat().st_size, "sha256": digest(image)},
               "package": {"file": package.relative_to(args.output).as_posix(), "sha256": digest(package)},
               "manifest": manifest, "sources": source_identity(), "toolchain": toolchain_identity,
               "data_preserved": ["/opt", "/root", "/mnt", "/srv"],
               "hardware_actions": False, "redistribution": "User-supplied RDA firmware included in the public release with explicit project-owner authorization"}
    (args.output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "image": receipt["image"], "root_space": manifest["root_space"]}))


if __name__ == "__main__":
    main()
