#!/usr/bin/env python3
"""Fail closed on native RAM-profile selection and actual resolved config."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from inspect_images import inspect_image


def check(source, built=False):
    config = (source / ".config").read_text()
    for option in (
            "TARGET_hi3798mv100", "TARGET_hi3798mv100_DEVICE_ty1208z_ca_ram",
            "TARGET_ROOTFS_INITRAMFS", "TARGET_INITRAMFS_COMPRESSION_GZIP", "USE_MUSL",
            "PACKAGE_ty1208z-time64", "BUSYBOX_CUSTOM", "BUSYBOX_CONFIG_STAT",
            "BUSYBOX_CONFIG_FEATURE_STAT_FORMAT"):
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"Native RAM profile did not resolve {option}=y")
    for option in ("TARGET_ROOTFS_SQUASHFS", "TARGET_ROOTFS_EXT4FS", "PACKAGE_mtd"):
        if f"CONFIG_{option}=y\n" in config:
            raise ValueError(f"Unexpected persistent-storage option: {option}")
    if (source / "feeds.conf").read_text() != "# RAM bring-up: no external feeds.\n":
        raise ValueError("Unexpected external feeds")
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for relative, expected in manifest.items():
        actual = hashlib.sha256((source / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Changed target input: {relative}")
    if built:
        kernels = list((source / "build_dir").glob("target-*/linux-hi3798mv100/linux-6.12.112/.config"))
        if len(kernels) != 1:
            raise ValueError("Expected one native kernel build")
        resolved = kernels[0].read_text()
        for option in ("ARCH_HI3798MV100", "HI3798MV100_TIMER", "SERIAL_AMBA_PL011_CONSOLE", "ARM_APPENDED_DTB"):
            if f"CONFIG_{option}=y\n" not in resolved:
                raise ValueError(f"Required native kernel option missing: {option}")
        for option in ("SMP", "BLOCK", "MTD", "MMC", "USB_SUPPORT", "PCI", "HI3798MV100_EMMC_AUDIT"):
            if f"CONFIG_{option}=y\n" in resolved or f"CONFIG_{option}=m\n" in resolved:
                raise ValueError(f"Unexpected native RAM kernel subsystem: {option}")
        images = list((source / "bin/targets/hi3798mv100").rglob("*initramfs*uImage-UNTESTED.bin"))
        if len(images) != 1:
            raise ValueError("Expected one native initramfs CA uImage")
        output = source / "bin/targets/hi3798mv100/checks"
        output.mkdir(parents=True, exist_ok=True)
        result = inspect_image(images[0], output)
        headers = result["uimages"]
        if (len(headers) != 1 or headers[0]["offset"] != 0
                or headers[0]["load_address"] != "0x2000000"
                or headers[0]["entry_address"] != "0x2000000"
                or not headers[0]["header_crc_valid"] or not headers[0]["payload_crc_valid"]
                or headers[0]["compression"] != 0
                or headers[0]["payload_bytes"] != result["bytes"] - 64
                or len(result["device_trees"]) != 1):
            raise ValueError("Native CA uImage/DTB structure differs or is corrupt")
        (output / "image.json").write_text(json.dumps(result, indent=2) + "\n")
        subprocess.run([
            sys.executable, str(Path(__file__).with_name("inspect_kernel_layout.py")),
            "--build", str(kernels[0].parent), "--output", str(output / "kernel-layout.json"),
        ], check=True)
        copied = kernels[0].parent.parent / "zImage-initramfs"
        if copied.read_bytes() != (kernels[0].parent / "arch/arm/boot/zImage").read_bytes():
            raise ValueError("Copied native initramfs kernel differs from the measured footprint")
        print(json.dumps(result, indent=2))
    print("OPENWRT_RAM_CONFIG_PASS" + ("; built, hardware untested" if built else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--built", action="store_true")
    args = parser.parse_args()
    check(args.source, args.built)


if __name__ == "__main__":
    main()
