"""Bounded external initrd for the exact native application kernel/rootfs pair."""
import gzip
import hashlib
import io
import json
import re
from pathlib import Path
from ethernet_net_profile import NETWORK_NODES, openwrt_router_ethernet_profile

# Keep the complete compressed archive below the unexplained bootloader
# Bound Addr (0x08e62000), clear of the measured kernel load/workspace.
INITRD_ADDRESS = 0x04000000
BOOTLOADER_BOUND_ADDRESS = 0x08E62000
# The dual-core rootfs passes both 512/240-MiB QEMU budgets. 36 MiB ends at
# 0x06400000, still well below the observed 0x08e62000 bootloader bound.
# Retain the 96-MiB expansion cap and exact-image bounded-memory acceptance.
MAX_COMPRESSED = 36 * 1024 * 1024
MAX_UNCOMPRESSED = 96 * 1024 * 1024
COMPATIBLE = "tianyi,ty1208z-ca-openwrt-apps-ram"
ROUTER_COMPATIBLE = "tianyi,ty1208z-ca-openwrt-router-ram"
BOOTARGS = "console=ttyAMA0,115200 earlycon=pl011,mmio32,0xf8b00000 rdinit=/init loglevel=7 panic=0"
BASE_PATHS = {"/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
              "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
              "/soc/timer@f8a29000", "/soc/serial@f8b00000"}
MARKERS = {"XRAY_UNSYNCHRONIZED_CLOCK_PASS", "NTP_ERA_TIME64_PASS", "CERTIFICATE_TIME64_PASS", "DNS_TIME64_PASS", "HTTPS_TIME64_PASS",
           "PASSWALL_LUCI_AUTH_TIME64_PASS", "LUCI_RPCD_TIME64_PASS",
           "PASSWALL_XRAY_SOCKS_TIME64_PASS", "PASSWALL_XRAY_TLS_TIME64_PASS",
           "NFT_EXPRESSIONS_AND_COUNTER_PASS", "OPENWRT_APPLICATIONS_QEMU_PASS"}
ROUTER_MARKERS = {"OPENWRT_ROUTER_FORWARDING_TIME64_PASS", "PASSWALL_TPROXY_TCP_TIME64_PASS",
                  "PASSWALL_TPROXY_UDP_TIME64_PASS"}
LANGUAGE_MARKER = "LUCI_CHINESE_DEFAULT_PASS"
DUAL_CORE_MARKERS = {"PASSWALL_SINGBOX_SOCKS_TIME64_PASS", "PASSWALL_SINGBOX_TLS_TIME64_PASS",
                     "UNZIP_ARCHIVE_TIME64_PASS", "LUCI_EMPTY_ROOT_LOGIN_PASS"}


def digest(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def validate_pair(artifacts):
    paths = {key: Path(artifacts) / name for key, name in (
        ("kernel", "zImage"), ("rootfs", "rootfs.cpio.gz"), ("config", "linux.config"),
        ("packages", "packages.manifest"), ("console", "checks/qemu-applications-256.log"))}
    report = json.loads((Path(artifacts) / "checks/applications-qemu-256.json").read_text())
    variant = report.get("application_variant", "qemu")
    markers = MARKERS | (ROUTER_MARKERS if variant == "ethernet" else set())
    # Preserve acceptance of earlier measured images. New builds record the
    # extra language check and must supply its actual console evidence too.
    if LANGUAGE_MARKER in report.get("passed_markers", []):
        markers = markers | {LANGUAGE_MARKER}
    if DUAL_CORE_MARKERS & set(report.get("passed_markers", [])):
        markers |= DUAL_CORE_MARKERS
    if (report.get("result") != "OPENWRT_APPLICATIONS_QEMU_PASS" or
            variant not in {"qemu", "ethernet"} or
            report.get("machine") != "virt,cortex-a7,single-core" or
            report.get("memory_mib") != 256 or report.get("memory_limit_mib") != 240 or
            report.get("clock_year") != 2040 or report.get("disks") is not False or
            report.get("host_network") is not False or set(report.get("passed_markers", [])) != markers):
        raise ValueError("Application RAM candidate lacks the bounded-memory/time64 acceptance")
    for name, path in paths.items():
        if digest(path.read_bytes()) != report.get("artifacts", {}).get(name):
            raise ValueError(f"Application kernel/rootfs/provenance identity differs: {name}")
    if ("CONFIG_TY1208Z_ETHERNET_INHERITED=y\n" in paths["config"].read_text()) != (variant == "ethernet"):
        raise ValueError("Application memory/runtime acceptance variant differs from the actual kernel")
    transcript = paths["console"].read_bytes().replace(b"\r", b"")
    if any(b"\n" + marker.encode() + b"\n" not in transcript for marker in markers):
        raise ValueError("Recorded application markers are absent from the actual console")
    data = paths["rootfs"].read_bytes()
    if not 0 < len(data) <= MAX_COMPRESSED:
        raise ValueError("Application initrd exceeds the compressed RAM budget")
    if INITRD_ADDRESS + len(data) >= BOOTLOADER_BOUND_ADDRESS:
        raise ValueError("Application initrd crosses the unresolved bootloader bound")
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        unpacked = stream.read(MAX_UNCOMPRESSED + 1)
    if len(unpacked) > MAX_UNCOMPRESSED or not unpacked.startswith(b"070701"):
        raise ValueError("Application initrd is not a bounded newc archive")
    packages = paths["packages"].read_text()
    for package in ("luci-app-passwall - ", "xray-core - ", "firewall4 - ", "dnsmasq-full - "):
        if package not in packages:
            raise ValueError(f"Native application manifest lacks {package}")
    if "sing-box - " in packages and not DUAL_CORE_MARKERS <= markers:
        raise ValueError("Dual-core application lacks bounded-memory runtime acceptance")
    if DUAL_CORE_MARKERS <= markers:
        for package in ("sing-box - ", "unzip - "):
            if package not in packages:
                raise ValueError(f"Native dual-core application manifest lacks {package}")
    return data, len(unpacked)


def applications_ram_profile(tree, config, artifacts):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    compatible = props["/"].get("compatible", {}).get("strings", [])
    chosen = props.get("/chosen", {})
    router = compatible == [ROUTER_COMPATIBLE, "hi3798mv100-series"]
    if compatible != [COMPATIBLE, "hi3798mv100-series"] and not router:
        if ({COMPATIBLE, ROUTER_COMPATIBLE} & set(compatible) or
                any(name.startswith("linux,initrd-") for name in chosen)):
            raise ValueError("External initrd outside the explicit application RAM profile")
        return None
    if set(props) != BASE_PATHS | (NETWORK_NODES if router else set()):
        raise ValueError("Unreviewed peripheral in application RAM profile")
    if router and not openwrt_router_ethernet_profile(tree, config):
        raise ValueError("Integrated application profile lacks its measured Ethernet drivers")
    expected = (
        ("/memory@0", "reg", "cells", [0, 0x10000000]),
        ("/cpus/cpu@0", "reg", "cells", [0]),
        ("/cpus/cpu@0", "compatible", "strings", ["arm,cortex-a7"]),
        ("/clock-24m", "clock-frequency", "cells", [24000000]),
        ("/clock-83m3", "clock-frequency", "cells", [83300000]),
        ("/interrupt-controller@f8a01000", "reg", "cells", [0xf8a01000, 0x1000, 0xf8a02000, 0x100]),
        ("/interrupt-controller@f8a01000", "compatible", "strings", ["arm,cortex-a7-gic"]),
        ("/soc/timer@f8a29000", "reg", "cells", [0xf8a29000, 0x20, 0xf8a2a000, 0x20]),
        ("/soc/timer@f8a29000", "interrupts", "cells", [0, 26, 4]),
        ("/soc/timer@f8a29000", "compatible", "strings", ["hisilicon,hi3798mv100-timer"]),
        ("/soc/serial@f8b00000", "reg", "cells", [0xf8b00000, 0x1000]),
        ("/soc/serial@f8b00000", "interrupts", "cells", [0, 49, 4]),
        ("/soc/serial@f8b00000", "compatible", "strings", ["arm,pl011", "arm,primecell"]),
        ("/soc/serial@f8b00000", "clock-names", "strings", ["uartclk", "apb_pclk"]),
        ("/chosen", "bootargs", "strings", [BOOTARGS]),
        ("/chosen", "stdout-path", "strings", ["serial0:115200n8"]),
        ("/aliases", "serial0", "strings", ["/soc/serial@f8b00000"]),
    )
    for path, name, kind, value in expected:
        if props[path].get(name, {}).get(kind) != value:
            raise ValueError(f"Application RAM resource differs: {path}/{name}")
    uart = props["/soc/serial@f8b00000"]
    if set(chosen) != {"bootargs", "stdout-path", "linux,initrd-start", "linux,initrd-end"}:
        raise ValueError("Unreviewed chosen property in application RAM profile")
    if "arm,primecell-periphid" in uart:
        raise ValueError("Application UART must use the real peripheral ID")
    xtal = props["/clock-24m"].get("phandle", {}).get("cells")
    uartclk = props["/clock-83m3"].get("phandle", {}).get("cells")
    if (not xtal or not uartclk or
            props["/soc/timer@f8a29000"].get("clocks", {}).get("cells") != xtal or
            uart.get("clocks", {}).get("cells") != uartclk * 2):
        raise ValueError("Application RAM clock connections differ")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    required = {"ARCH_HI3798MV100", "HI3798MV100_TIMER", "ARM_APPENDED_DTB", "BLK_DEV_INITRD",
                "RD_GZIP", "NET", "INET", "MODULES", "NETFILTER", "NF_TABLES"}
    prohibited = {"BLOCK", "MMC", "MTD", "ATA", "SCSI", "USB_SUPPORT", "SMP", "HISI_FEMAC",
                  "ARM_ATAG_DTB_COMPAT", "INITRAMFS_FORCE", "CMDLINE_FORCE",
                  "HI3798MV100_USB_AUDIT", "HI3798MV100_EMMC_AUDIT",
                  "MMC_DW_HI3798MV100_IDENT", "HI3798MV100_ETHERNET_AUDIT",
                  "HI3798MV100_ETHERNET_CLOCK_ID", "TY1208Z_ETHERNET_INHERITED",
                  "POWER_RESET_TY1208Z_SP805"}
    release = "-ty1208z-openwrt-router" if router else "-ty1208z-openwrt-ram"
    if router:
        prohibited -= {"HISI_FEMAC", "TY1208Z_ETHERNET_INHERITED"}
    if (not required <= active or active & prohibited or
            f'CONFIG_LOCALVERSION="{release}"\n' not in config or
            'CONFIG_INITRAMFS_SOURCE=""\n' not in config):
        raise ValueError("Invalid native application RAM kernel configuration")
    data, unpacked_bytes = validate_pair(artifacts)
    end = INITRD_ADDRESS + len(data)
    if (chosen.get("linux,initrd-start", {}).get("cells") != [INITRD_ADDRESS] or
            chosen.get("linux,initrd-end", {}).get("cells") != [end]):
        raise ValueError("External initrd DT range differs from the exact validated archive")
    return {"file": "rootfs.cpio.gz", "address": INITRD_ADDRESS,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "uncompressed_bytes": unpacked_bytes}
