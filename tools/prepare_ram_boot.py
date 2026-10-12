#!/usr/bin/env python3
"""Validate a bounded RAM diagnostic plan from measured bootloader responses."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

from inspect_images import parse_fdt
from emmc_profiles import identification_profile
from ethernet_profiles import ethernet_audit_profile, ethernet_clock_id_profile
from ethernet_net_profile import ethernet_net_profile, openwrt_ethernet_profile
from usb_audit_profile import usb_audit_profile
from restart_profile import restart_profile
from openwrt_apps_ram_profile import BOOTLOADER_BOUND_ADDRESS, applications_ram_profile

ADDRESS = 0x01FFFFC0
DDR_START = 0x01000000
DDR_END = 0x40000000
DIAGNOSTIC_END = 0x10000000
# Measured original boot allocations all lie above this bound. The diagnostic
# memory and transfer footprint must remain below it; do not treat ddrfree as
# a dynamic allocator/reservation map.
BOOT_ALLOCATIONS_START = 0x3E507000


def prepare(artifacts, inspection):
    metadata = json.loads(inspection.read_text(encoding="utf-8"))
    raw = inspection.parent / metadata["raw_file"]
    response = raw.read_bytes()
    if (metadata.get("stop_reason") != "probe-complete"
            or hashlib.sha256(response).hexdigest() != metadata["raw_sha256"]):
        raise ValueError("Inspection is incomplete or the raw digest differs")
    if b"DDR free region baseaddr:0x1000000 size:0x3F000000" not in response:
        raise ValueError("Measured DDR report is missing or differs")
    if b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0" not in response:
        raise ValueError("Existing Hinas image address differs")
    for required in (b"Fastboot 3.3.0-dirty ", b"loady [ off ] [ baud ]",
                     b"crc32 address count [addr]", b"bootm [addr [arg ...]]"):
        if required not in response:
            raise ValueError(f"Required measured command/version missing: {required!r}")
    data = (artifacts / "uImage-UNTESTED.bin").read_bytes()
    zimage = (artifacts / "zImage").read_bytes()
    dtb = (artifacts / "ty1208z-diagnostic.dtb").read_bytes()
    if data[64:] != zimage + dtb:
        raise ValueError("Image does not contain exactly the candidate zImage and appended DTB")
    fields = struct.unpack_from(">7I4B32s", data)
    magic, hcrc, _, size, load, entry, dcrc, os_type, arch, image_type, compression, _ = fields
    header = data[:4] + b"\0" * 4 + data[8:64]
    if (magic != 0x27051956 or zlib.crc32(header) != hcrc or len(data) != 64 + size
            or zlib.crc32(data[64:]) != dcrc or (os_type, arch, image_type, compression) != (5, 2, 2, 0)
            or load != 0x02000000 or entry != load):
        raise ValueError("Unexpected or corrupt ordinary ARM diagnostic uImage")
    if struct.unpack_from("<I", zimage, 0x24)[0] != 0x016F2818:
        raise ValueError("Missing ARM zImage header")
    if not DDR_START <= ADDRESS < ADDRESS + len(data) + 0x100000 < DIAGNOSTIC_END < BOOT_ALLOCATIONS_START:
        raise ValueError("Transfer/decompressor workspace overlaps bounded memory ranges")
    tree = parse_fdt(dtb)
    properties = {node["path"]: node["properties"] for node in tree["nodes"]}
    if properties["/memory@0"]["reg"]["cells"] != [0, DIAGNOSTIC_END]:
        raise ValueError("Unexpected diagnostic memory size/base")
    reserve_offset = struct.unpack_from(">I", dtb, 16)[0]
    reservations = []
    while reserve_offset + 16 <= len(dtb):
        start, length = struct.unpack_from(">QQ", dtb, reserve_offset)
        reserve_offset += 16
        if start == length == 0:
            break
        reservations.append((start, length))
    if (0, DDR_START) not in reservations:
        raise ValueError("Low 16 MiB allocation reservation is missing")
    layout = json.loads((artifacts / "checks/kernel-layout.json").read_text())
    if (layout["zimage_sha256"] != hashlib.sha256(zimage).hexdigest()
            or layout["physical_start"] != 0x8000
            or not layout["physical_start"] < layout["physical_image_end"] <= layout["physical_bss_end"] < DDR_START):
        raise ValueError("Kernel layout does not match this image or exceeds the low bound")
    config = (artifacts / "linux.config").read_text()
    ident = identification_profile(tree, config)
    ethernet_audit_profile(tree, config)
    ethernet_clock_id_profile(tree, config)
    usb_audit_profile(tree, config)
    restart_profile(tree, config)
    application_initrd = applications_ram_profile(tree, config, artifacts)
    if properties["/"]["compatible"].get("strings", [None])[0] == "tianyi,ty1208z-ca-openwrt-net":
        network = openwrt_ethernet_profile(tree, config)
        if not network:
            raise ValueError("Native Ethernet profile lacks its built-in hardware drivers")
    else:
        network = ethernet_net_profile(tree, config)
    for name in ("BLOCK", "MMC", "MTD", "ATA", "SCSI", "NET", "USB_SUPPORT", "MODULES", "SMP"):
        if name == "MMC" and ident:
            continue
        if name == "NET" and network:
            continue
        if name in ("NET", "MODULES") and application_initrd is not None:
            continue
        if re.search(rf"^CONFIG_{name}=[ym]$", config, re.MULTILINE):
            raise ValueError(f"Unexpected diagnostic subsystem enabled: {name}")
    plan = {
        "schema": 1, "status": "validated placement candidate; hardware boot untested",
        "image_bytes": len(data), "image_sha256": hashlib.sha256(data).hexdigest(),
        "image_crc32": f"{zlib.crc32(data):08x}", "header_address": ADDRESS,
        "load_address": load, "entry_address": entry,
        "kernel_layout": layout, "inspection_raw_sha256": metadata["raw_sha256"],
        "load_command": f"loady {ADDRESS:x} 115200",
        "crc_command": f"crc32 {ADDRESS:x} {len(data):x}",
        "boot_command": f"bootm {ADDRESS:x}",
        "persistent_writes": False,
    }
    if application_initrd is not None:
        start = application_initrd["address"]
        end = start + application_initrd["bytes"]
        if not ADDRESS + len(data) + 0x100000 < start < end < BOOTLOADER_BOUND_ADDRESS < DIAGNOSTIC_END:
            raise ValueError("External initrd overlaps the kernel load/workspace or bounded RAM end")
        initrd_bytes = (artifacts / application_initrd["file"]).read_bytes()
        plan["additional_loads"] = [{**application_initrd,
            "load_command": f"loady {start:x} 115200",
            "crc_command": f"crc32 {start:x} {len(initrd_bytes):x}",
            "image_crc32": f"{zlib.crc32(initrd_bytes):08x}"}]
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(args.artifacts, args.inspection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
