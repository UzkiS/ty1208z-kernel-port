#!/usr/bin/env python3
"""Package an unchanged tested native application kernel and separate initrd for RAM only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from check_openwrt_applications import check
from inspect_images import inspect_image, parse_fdt
from openwrt_apps_ram_profile import INITRD_ADDRESS, applications_ram_profile, digest, validate_pair
from prepare_openwrt_applications import application_variant

PROJECT = Path(__file__).resolve().parents[1]


def unique(paths, label):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError(f"Expected exactly one {label}")
    return paths[0]


def make(source, output):
    if (source / ".ty1208z-container-compile-only.json").exists():
        raise ValueError("Compile-only container packages must not become a board RAM image")
    check(source, built=True)
    variant = application_variant(source)
    ethernet = variant in ("ethernet", "ethernet-ram768")
    layer = "router768" if variant == "ethernet-ram768" else "router" if ethernet else "applications"
    if output is None:
        output = PROJECT / ("artifacts/openwrt-router768" if variant == "ethernet-ram768" else
                            "artifacts/openwrt-router1" if ethernet else "artifacts/openwrt-apps-ram1")
    kernel = unique((source / "build_dir").glob("target-*/linux-hi3798mv100_apps/linux-6.12.112"), "application kernel")
    images = source / "bin/targets/hi3798mv100/apps"
    output.mkdir(parents=True, exist_ok=True)
    checks = output / "checks"
    checks.mkdir(exist_ok=True)
    # A failed rerun must not leave a stale wrapped image/acceptance manifest.
    for name in ("uImage-UNTESTED.bin", "manifest.json"):
        (output / name).unlink(missing_ok=True)
    for path, name in (
            (kernel / "arch/arm/boot/zImage", "zImage"), (kernel / ".config", "linux.config"),
            (unique(images.glob("*rootfs.cpio.gz"), "application rootfs"), "rootfs.cpio.gz"),
            (unique(images.glob("*.manifest"), "application package manifest"), "packages.manifest")):
        shutil.copyfile(path, output / name)
    for name in ("applications-qemu-256.json", "qemu-applications-256.log"):
        shutil.copyfile(images / "checks" / name, checks / name)
    rootfs, _ = validate_pair(output)
    board_sources = ["arch/arm/mach-hisi/hi3798mv100.c", "drivers/clocksource/timer-hi3798mv100.c"]
    if ethernet:
        board_sources += ["drivers/clk/hisilicon/clk-ty1208z-ethernet.c",
                          "drivers/clk/hisilicon/ty1208z-ethernet-gate.h",
                          "drivers/net/phy/festa-ty1208z.c",
                          "drivers/net/ethernet/hisilicon/hi3798mv100-femac.h"]
    for name in board_sources:
        if (kernel / name).read_bytes() != (PROJECT / "overlay" / name).read_bytes():
            raise ValueError(f"Native application kernel board source differs: {name}")
    if ethernet:
        subprocess.run([sys.executable, str(PROJECT / "tools/test_ethernet_probe_guards.py"),
                        "--linux", str(kernel)], check=True)
        subprocess.run([sys.executable, str(PROJECT / "tools/test_femac_datapath.py"),
                        "--linux", str(kernel)], check=True)
    if variant == "ethernet-ram768":
        from test_ram768 import actual_init_memory
        actual_init_memory(kernel)
    subprocess.run([sys.executable, str(PROJECT / "tools/inspect_kernel_layout.py"),
                    "--build", str(kernel), "--output", str(checks / "kernel-layout.json")], check=True)
    cpp = subprocess.run([
        "cc", "-E", "-nostdinc", "-undef", "-D__DTS__", "-x", "assembler-with-cpp",
        f"-DTY1208Z_INITRD_START=0x{INITRD_ADDRESS:x}",
        f"-DTY1208Z_INITRD_END=0x{INITRD_ADDRESS + len(rootfs):x}",
        "-I", str(PROJECT / "overlay/arch/arm/boot/dts/hisilicon"), "-I", str(kernel / "include"),
        str(PROJECT / "openwrt" / layer / "ram-rootfs.dts"),
    ], stdout=subprocess.PIPE, check=True).stdout
    preprocessed = checks / "applications-ram.dts"
    preprocessed.write_bytes(cpp)
    dtb = output / "ty1208z-diagnostic.dtb"
    subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb), str(preprocessed)], check=True)
    tree = parse_fdt(dtb.read_bytes())
    initrd = applications_ram_profile(tree, (output / "linux.config").read_text(), output)
    if initrd is None:
        raise ValueError("Compiled application RAM profile missing")
    payload = output / "zImage-appended-dtb"
    payload.write_bytes((output / "zImage").read_bytes() + dtb.read_bytes())
    subprocess.run(["mkimage", "-A", "arm", "-O", "linux", "-T", "kernel", "-C", "none",
                    "-a", "0x02000000", "-e", "0x02000000", "-n", "TY1208Z apps external initrd RAM",
                    "-d", str(payload), str(output / "uImage-UNTESTED.bin")], check=True,
                   env={**os.environ, "SOURCE_DATE_EPOCH": "1791676800", "TZ": "UTC"})
    image = inspect_image(output / "uImage-UNTESTED.bin", checks)
    header = image["uimages"][0]
    if (len(image["uimages"]) != 1 or not header["header_crc_valid"] or
            not header["payload_crc_valid"] or image["bytes"] >= 20 * 1024 * 1024):
        raise ValueError("Invalid application RAM uImage")
    (checks / "image-validation.json").write_text(json.dumps(image, indent=2) + "\n")
    manifest = {"status": "native application RAM placement candidate; hardware untested; no install recipe",
                "application_variant": variant,
                "external_initrd": initrd,
                "files": {name: digest((output / name).read_bytes()) for name in (
                    "uImage-UNTESTED.bin", "zImage", "ty1208z-diagnostic.dtb", "linux.config",
                    "rootfs.cpio.gz", "packages.manifest")}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("OPENWRT_APPS_RAM_PACKAGED: unchanged matched kernel/modules/rootfs, separate bounded initrd; hardware untested")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    make(args.source.resolve(), args.output.resolve() if args.output else None)


if __name__ == "__main__":
    main()
