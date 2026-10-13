#!/usr/bin/env python3
"""Check selected native applications without claiming any board acceptance."""
import argparse
import json
from pathlib import Path
import re

from prepare_openwrt import sha256
from prepare_openwrt_applications import application_variant


def check(source, built=False):
    ethernet = application_variant(source) == "ethernet"
    config = (source / ".config").read_text()
    for option in (
            "TARGET_hi3798mv100_apps", "TARGET_hi3798mv100_apps_DEVICE_ty1208z_apps",
            "TARGET_ROOTFS_INITRAMFS_SEPARATE", "USE_MUSL", "PACKAGE_luci-app-passwall",
            "LUCI_LANG_zh_Hans", "PACKAGE_luci-i18n-base-zh-cn",
            "PACKAGE_luci-i18n-firewall-zh-cn", "PACKAGE_luci-i18n-passwall-zh-cn",
            "PACKAGE_luci-app-passwall_Nftables_Transparent_Proxy", "PACKAGE_xray-core",
            "PACKAGE_luci-app-passwall_INCLUDE_Xray", "PACKAGE_luci-app-passwall_INCLUDE_SingBox",
            "PACKAGE_sing-box", "PACKAGE_unzip",
            "PACKAGE_firewall4", "PACKAGE_dnsmasq-full", "PACKAGE_ty1208z-time64",
            "LIBCURL_THREADED_RESOLVER"):
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"Application profile did not resolve {option}=y")
    for option in ("TARGET_hi3798mv100_ram", "TARGET_ROOTFS_SQUASHFS", "TARGET_ROOTFS_EXT4FS", "PACKAGE_mtd"):
        if f"CONFIG_{option}=y\n" in config:
            raise ValueError(f"Unexpected application-profile option: {option}")
    if ethernet:
        for option in ("PACKAGE_iperf3", "PACKAGE_ethtool", "PACKAGE_ip-full", "PACKAGE_kmod-veth",
                       "KERNEL_NAMESPACES", "KERNEL_NET_NS"):
            if f"CONFIG_{option}=y\n" not in config:
                raise ValueError(f"Integrated application Ethernet option missing: {option}")
        if "CONFIG_KERNEL_DEBUG_FS=y\n" in config:
            raise ValueError("Integrated Ethernet experiment unexpectedly enables debugfs")
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
    for item in lock.get("source_patches", []):
        feed = source / "feeds" / item["feed"]
        if (sha256(feed / item["recipe"]) != item["recipe_sha256"] or
                sha256(feed / item["path"]) != item["sha256"]):
            raise ValueError(f"Application source patch identity differs: {item['path']}")
    if built:
        for item in lock.get("source_patches", []):
            patched = list((source / "build_dir").glob(f"target-*/{item['source_root']}/{item['source_file']}"))
            if len(patched) != 1 or sha256(patched[0]) != item["patched_sha256"]:
                raise ValueError(f"Actual application source lacks the checked patch: {item['source_file']}")
        kernels = list((source / "build_dir").glob(
            "target-*/linux-hi3798mv100_apps/linux-6.12.112/.config"))
        if len(kernels) != 1:
            raise ValueError("Expected one built application kernel configuration")
        kernel_config = kernels[0].read_text()
        for option in ("BLOCK", "MMC", "MTD", "USB_SUPPORT", "SMP",
                       "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT"):
            if re.search(rf"^CONFIG_{option}=[ym]$", kernel_config, re.MULTILINE):
                raise ValueError(f"Unreviewed hardware subsystem in application kernel: {option}")
        if ethernet:
            for option in ("HISI_FEMAC", "MDIO_HISI_FEMAC", "TY1208Z_ETHERNET_INHERITED",
                           "FESTA_TY1208Z_PHY", "PHYLIB", "NET_NS"):
                if f"CONFIG_{option}=y\n" not in kernel_config:
                    raise ValueError(f"Missing built-in integrated Ethernet option: {option}")
            if 'CONFIG_LOCALVERSION="-ty1208z-openwrt-router"\n' not in kernel_config:
                raise ValueError("Integrated application kernel release differs")
            for option in ("WIRELESS", "WLAN", "DEBUG_FS"):
                if re.search(rf"^CONFIG_{option}=[ym]$", kernel_config, re.MULTILINE):
                    raise ValueError(f"Unexpected integrated Ethernet subsystem: {option}")
        elif re.search(r"^CONFIG_HISI_FEMAC=[ym]$", kernel_config, re.MULTILINE):
            raise ValueError("Plain application kernel unexpectedly enables board Ethernet")
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
        root_accounts = [line.split(":") for line in (rootfs / "etc/shadow").read_text().splitlines()
                         if line.startswith("root:")]
        if len(root_accounts) != 1 or len(root_accounts[0]) != 9 or root_accounts[0][1] != "":
            raise ValueError("Application rootfs must default to an empty root password")
        language_default = Path("etc/uci-defaults/99-ty1208z-luci-language")
        expected_language = (Path(__file__).resolve().parents[1] /
                            "openwrt/applications/overlay/target/linux/hi3798mv100/base-files" /
                            language_default).read_bytes()
        if (rootfs / language_default).read_bytes() != expected_language:
            raise ValueError("Application rootfs lacks the reviewed Chinese language default")
        for name in ("base", "firewall", "passwall"):
            translation = rootfs / f"usr/lib/lua/luci/i18n/{name}.zh-cn.lmo"
            if not translation.is_file() or translation.stat().st_size == 0:
                raise ValueError(f"Application rootfs lacks Chinese translation: {name}")
        ntpd = rootfs / "usr/sbin/ntpd"
        if (not ntpd.is_symlink() or ntpd.readlink() != Path("../../bin/busybox") or
                not (rootfs / "bin/busybox").is_file() or
                not (rootfs / "etc/init.d/sysntpd").is_file()):
            raise ValueError("Actual application rootfs lacks the installed BusyBox NTP service")
        if list(rootfs.rglob("ntp-qemu-fixture*")) or list(rootfs.rglob("ntp-runtime-test*")):
            raise ValueError("QEMU-only NTP fixture must not enter the delivered rootfs")
        if ethernet:
            expected = (Path(__file__).resolve().parents[1] / "openwrt/router/overlay/target/linux/"
                        "hi3798mv100/base-files/etc/config/network").read_bytes()
            if (rootfs / "etc/config/network").read_bytes() != expected:
                raise ValueError("Integrated netifd rootfs differs from reviewed DHCP-client selection")
            for name in ("usr/bin/iperf3", "usr/sbin/ethtool", "usr/libexec/ip-full"):
                if not (rootfs / name).is_file():
                    raise ValueError(f"Integrated rootfs lacks runtime tool: {name}")
            # OpenWrt exposes ip through an absolute target-root symlink. The
            # target is checked above; Path.is_file() on the build host cannot
            # follow that target outside this staging root.
            if (not (rootfs / "sbin/ip").is_symlink() or
                    str((rootfs / "sbin/ip").readlink()) != "/usr/libexec/ip-full"):
                raise ValueError("Integrated rootfs lacks the /sbin/ip wrapper")
        for name in ("usr/bin/xray", "usr/bin/sing-box", "usr/bin/unzip", "usr/share/passwall/app.sh"):
            if not (rootfs / name).is_file() or (rootfs / name).is_symlink():
                raise ValueError(f"Actual application rootfs is missing installed application: {name}")
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
        for package in ("luci-app-passwall - ", "xray-core - ", "sing-box - ", "unzip - ",
                        "firewall4 - ", "dnsmasq-full - ",
                        "luci-i18n-base-zh-cn - ", "luci-i18n-firewall-zh-cn - ",
                        "luci-i18n-passwall-zh-cn - "):
            if package not in packages:
                raise ValueError(f"Application not installed in actual rootfs: {package}")
    print("OPENWRT_APPLICATION_CONFIG_PASS variant=" + ("ethernet" if ethernet else "qemu") +
          ("; built, runtime/hardware untested" if built else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--built", action="store_true")
    args = parser.parse_args()
    check(args.source, args.built)


if __name__ == "__main__":
    main()
