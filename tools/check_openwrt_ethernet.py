#!/usr/bin/env python3
"""Validate actual native Ethernet output and export it for guarded RAM boot."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from ethernet_net_profile import openwrt_ethernet_profile
from inspect_images import inspect_image, parse_fdt
from prepare_openwrt import sha256

PROJECT = Path(__file__).resolve().parents[1]


def check(source, built=False):
    config = (source / ".config").read_text()
    for option in ("TARGET_hi3798mv100", "TARGET_hi3798mv100_net",
                   "TARGET_hi3798mv100_net_DEVICE_ty1208z_ca_net", "USE_MUSL",
                   "TARGET_ROOTFS_INITRAMFS", "TARGET_INITRAMFS_COMPRESSION_GZIP",
                   "PACKAGE_ty1208z-time64", "PACKAGE_iperf3", "PACKAGE_libiperf3",
                   "PACKAGE_ethtool", "BUSYBOX_CONFIG_FEATURE_FANCY_PING",
                   "BUSYBOX_CONFIG_SHA256SUM", "BUSYBOX_CONFIG_HTTPD", "BUSYBOX_CONFIG_NC",
                   "BUSYBOX_CONFIG_NC_SERVER", "BUSYBOX_CONFIG_TIMEOUT"):
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"Native Ethernet option missing: {option}")
    for option in ("TARGET_hi3798mv100_ram", "TARGET_ROOTFS_INITRAMFS_SEPARATE",
                   "TARGET_ROOTFS_SQUASHFS", "TARGET_ROOTFS_EXT4FS", "PACKAGE_mtd",
                   "PACKAGE_dnsmasq", "PACKAGE_dropbear", "PACKAGE_firewall4"):
        if f"CONFIG_{option}=y\n" in config:
            raise ValueError(f"Unexpected Ethernet experiment option: {option}")
    for option in ("IPV6", "KERNEL_IPV6", "KERNEL_DEBUG_FS"):
        if f"CONFIG_{option}=y\n" in config:
            raise ValueError(f"Unexpected native Ethernet experiment subsystem: {option}")
    if (source / "feeds.conf").read_text() != "# RAM bring-up: no external feeds.\n":
        raise ValueError("Ethernet experiment must not use application feeds")
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for relative, expected in manifest.items():
        if sha256(source / relative) != expected:
            raise ValueError(f"Changed Ethernet target input: {relative}")
    if not built:
        print("OPENWRT_ETHERNET_CONFIG_PASS")
        return
    kernels = list((source / "build_dir").glob("target-*/linux-hi3798mv100_net/linux-6.12.112"))
    images = list((source / "bin/targets/hi3798mv100/net").glob("*initramfs*uImage-UNTESTED.bin"))
    roots = list((source / "build_dir").glob("target-*/root-hi3798mv100"))
    if len(kernels) != 1 or len(images) != 1 or len(roots) != 1:
        raise ValueError("Expected one native Ethernet kernel, image and rootfs")
    kernel, image, root = kernels[0], images[0], roots[0]
    release = (kernel / "include/generated/utsrelease.h").read_text().strip()
    if release != '#define UTS_RELEASE "6.12.112"':
        raise ValueError("Native Ethernet compiled kernel release differs from the measured OpenWrt release")
    output = PROJECT / "artifacts/openwrt-net1"
    checks = output / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    result = inspect_image(image, checks)
    headers = result["uimages"]
    if (len(headers) != 1 or headers[0]["offset"] != 0 or
            headers[0]["load_address"] != "0x2000000" or
            headers[0]["entry_address"] != "0x2000000" or
            not headers[0]["header_crc_valid"] or not headers[0]["payload_crc_valid"] or
            headers[0]["compression"] != 0 or
            headers[0]["payload_bytes"] != result["bytes"] - 64 or len(result["device_trees"]) != 1):
        raise ValueError("Corrupt or changed native Ethernet uImage structure")
    tree = result["device_trees"][0]
    dtb = checks / tree["extracted_file"]
    resolved = (kernel / ".config").read_text()
    if not openwrt_ethernet_profile(parse_fdt(dtb.read_bytes()), resolved):
        raise ValueError("Missing exact native Ethernet DT/config profile")
    for option in ("ARCH_HI3798MV100", "HI3798MV100_TIMER", "SERIAL_AMBA_PL011_CONSOLE",
                   "ARM_APPENDED_DTB", "CPU_LITTLE_ENDIAN", "KERNEL_GZIP"):
        if f"CONFIG_{option}=y\n" not in resolved:
            raise ValueError(f"Missing native board kernel option: {option}")
    subprocess.run([sys.executable, str(PROJECT / "tools/inspect_kernel_layout.py"),
                    "--build", str(kernel), "--output", str(checks / "kernel-layout.json")], check=True)
    zimage = kernel / "arch/arm/boot/zImage"
    if ((kernel.parent / "zImage-initramfs").read_bytes() != zimage.read_bytes() or
            image.read_bytes()[64:] != zimage.read_bytes() + dtb.read_bytes()):
        raise ValueError("Native image differs from measured actual kernel/DTB")
    for name in ("usr/bin/iperf3", "usr/sbin/ethtool", "bin/busybox", "usr/bin/time64-probe"):
        if not (root / name).is_file():
            raise ValueError(f"Actual native rootfs missing tool: {name}")
    network = (root / "etc/config/network").read_bytes()
    expected = (PROJECT / "openwrt/ethernet/overlay/target/linux/hi3798mv100/base-files/etc/config/network").read_bytes()
    if network != expected:
        raise ValueError("Actual netifd configuration differs from reviewed DHCP-only selection")
    for source_path, name in ((image, "uImage-UNTESTED.bin"), (zimage, "zImage"),
                              (dtb, "ty1208z-diagnostic.dtb"), (kernel / ".config", "linux.config")):
        shutil.copyfile(source_path, output / name)
    # Verify commands from the actual dynamically linked ARM BusyBox, not the
    # host applet or merely the requested Kconfig fragment.
    # The native BusyBox disables FEATURE_INSTALLER, so '--list' itself is
    # unavailable. Exercise the actual applets directly instead.
    for applet in ("ping", "sha256sum", "httpd", "nc", "timeout"):
        help_output = subprocess.run([
            "qemu-arm", "-L", str(root), str(root / "bin/busybox"), applet, "--help"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout
        if f"Usage: {applet} ".encode() not in help_output:
            raise ValueError(f"Native ARM BusyBox lacks usable traffic applet: {applet}")
    usage = subprocess.run(["qemu-arm", "-L", str(root), str(root / "bin/busybox"), "ping", "--help"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout
    if b"-c CNT" not in usage or b"-I IFACE" not in usage:
        raise ValueError("Native ARM ping lacks bounded/interface selection")
    (checks / "image.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "manifest.json").write_text(json.dumps({
        "status": "native RAM Ethernet candidate; hardware untested",
        "kernel_release": "6.12.112",
        "files": {name: {"bytes": (output / name).stat().st_size, "sha256": sha256(output / name)}
                  for name in ("uImage-UNTESTED.bin", "zImage", "ty1208z-diagnostic.dtb", "linux.config")},
        "toolchain": json.loads((source / ".ty1208z-toolchain.json").read_text()),
        "traffic_tools": {name: sha256(root / name) for name in ("usr/bin/iperf3", "bin/busybox")},
    }, indent=2) + "\n")
    print(f"OPENWRT_ETHERNET_BUILT_PASS: {result['bytes']} bytes; hardware untested")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--built", action="store_true")
    args = parser.parse_args()
    check(args.source, args.built)


if __name__ == "__main__":
    main()
