#!/usr/bin/env python3
"""Check selected native applications without claiming any board acceptance."""
import argparse
import json
from pathlib import Path
import re

from prepare_openwrt import sha256


def check(source, built=False):
    config = (source / ".config").read_text()
    for option in (
            "TARGET_hi3798mv100_apps", "TARGET_hi3798mv100_apps_DEVICE_ty1208z_apps",
            "TARGET_ROOTFS_INITRAMFS_SEPARATE", "USE_MUSL", "PACKAGE_luci-app-passwall",
            "PACKAGE_luci-app-passwall_Nftables_Transparent_Proxy", "PACKAGE_xray-core",
            "PACKAGE_firewall4", "PACKAGE_dnsmasq-full", "PACKAGE_ty1208z-time64",
            "LIBCURL_THREADED_RESOLVER"):
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"Application profile did not resolve {option}=y")
    for option in ("TARGET_hi3798mv100_ram", "TARGET_ROOTFS_SQUASHFS", "TARGET_ROOTFS_EXT4FS", "PACKAGE_mtd"):
        if f"CONFIG_{option}=y\n" in config:
            raise ValueError(f"Unexpected application-profile option: {option}")
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for relative, expected in manifest.items():
        if sha256(source / relative) != expected:
            raise ValueError(f"Changed application input: {relative}")
    lock = json.loads((source / ".ty1208z-application-lock.json").read_text())
    for item in lock["feeds"]:
        feed = source / "feeds" / item["name"]
        if json.loads((feed / ".ty1208z-feed.json").read_text()) != item:
            raise ValueError(f"Feed identity differs: {item['name']}")
    for item in lock.get("recipe_patches", []):
        if sha256(source / "feeds" / item["feed"] / item["path"]) != item["patched_sha256"]:
            raise ValueError(f"Patched recipe identity differs: {item['path']}")
    if built:
        kernels = list((source / "build_dir").glob(
            "target-*/linux-hi3798mv100_apps/linux-6.12.112/.config"))
        if len(kernels) != 1:
            raise ValueError("Expected one built application kernel configuration")
        kernel_config = kernels[0].read_text()
        for option in ("BLOCK", "MMC", "MTD", "USB_SUPPORT", "SMP", "HISI_FEMAC",
                       "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT"):
            if re.search(rf"^CONFIG_{option}=[ym]$", kernel_config, re.MULTILINE):
                raise ValueError(f"Unreviewed hardware subsystem in application kernel: {option}")
        images = list((source / "bin/targets/hi3798mv100/apps").glob("*uImage*"))
        if images:
            raise ValueError("Application validation must not emit a CA board image")
        # No per-device image means OpenWrt does not create profiles.json here.
        profiles_path = source / "bin/targets/hi3798mv100/apps/profiles.json"
        if profiles_path.exists():
            profiles = json.loads(profiles_path.read_text())
            if set(profiles["profiles"]) - {"ty1208z_apps"}:
                raise ValueError("Application image recipes selected a different device")
        roots = list((source / "build_dir").glob("target-*/root-hi3798mv100"))
        if len(roots) != 1:
            raise ValueError("Expected one actual application rootfs")
        rootfs = roots[0]
        if not (rootfs / "usr/bin/xray").is_file() or not (rootfs / "usr/share/passwall/app.sh").is_file():
            raise ValueError("Actual application rootfs is missing Xray or Passwall")
        for item in lock.get("recipe_patches", []):
            if "installed_path" not in item:
                continue
            installed = rootfs / item["installed_path"]
            if not installed.resolve().is_relative_to(rootfs.resolve()):
                raise ValueError("Installed patch path escapes rootfs")
            if sha256(installed) != item["patched_sha256"]:
                raise ValueError(f"Actual rootfs lacks the checked patch: {item['installed_path']}")
        manifests = list((source / "bin/targets/hi3798mv100/apps").glob("*.manifest"))
        if len(manifests) != 1:
            raise ValueError("Expected one built application package manifest")
        manifest_path = manifests[0]
        packages = manifest_path.read_text()
        for package in ("luci-app-passwall - ", "xray-core - ", "firewall4 - ", "dnsmasq-full - "):
            if package not in packages:
                raise ValueError(f"Application not installed in actual rootfs: {package}")
    print("OPENWRT_APPLICATION_CONFIG_PASS" + ("; built, runtime/hardware untested" if built else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--built", action="store_true")
    args = parser.parse_args()
    check(args.source, args.built)


if __name__ == "__main__":
    main()
