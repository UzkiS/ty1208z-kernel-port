#!/usr/bin/env python3
"""Read-only wireless clues from local filesystem images using 7-Zip."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--sevenzip", type=Path, default=Path(r"C:\Program Files\7-Zip\7z.exe"))
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()

def modinfo(blob):
    if blob[:6] != b"\x7fELF\x01\x01":
        return {"error": "Not little-endian ELF32"}
    section_offset = struct.unpack_from("<I", blob, 32)[0]
    entry_size, count, names_index = struct.unpack_from("<HHH", blob, 46)
    sections = [struct.unpack_from("<10I", blob, section_offset + index * entry_size)
                for index in range(count)]
    names_section = sections[names_index]
    names = blob[names_section[4]:names_section[4] + names_section[5]]
    for section in sections:
        name = names[section[0]:].split(b"\0")[0]
        if name == b".modinfo":
            payload = blob[section[4]:section[4] + section[5]]
            properties = {}
            for item in payload.split(b"\0"):
                if b"=" in item:
                    key, value = item.decode("utf-8", "replace").split("=", 1)
                    properties.setdefault(key, []).append(value)
            return properties
    return {"error": "No .modinfo section"}

report = {"status": "Firmware clues only; physical Wi-Fi chip unidentified",
          "backup_provenance": "Android backup XML points to M301H; not proven to belong to TY1208Z",
          "images": []}
paths = [args.workspace / "TTL-hi3798mv100-32bit/rootfs-32.img"]
paths += list(args.workspace.glob("*/17.system.img"))
for path in paths:
    result = subprocess.run([str(args.sevenzip), "l", "-ba", str(path)],
                            capture_output=True, check=True)
    listing = result.stdout.decode("utf-8", "replace")
    clues = [line for line in listing.splitlines()
             if re.search(r"wifi|wlan|wireless|rtl\d|rda599|rdawfmac|cfg80211|mac80211|brcm|ath\d|mt76", line, re.I)]
    entry = {"file": str(path.relative_to(args.workspace)), "bytes": path.stat().st_size,
             "wireless_listing": clues, "modules": []}
    for line in clues:
        match = re.search(r"  (\S+\.ko)$", line)
        if not match or not re.search(r"rtl8188|rdawfmac", match[1], re.I):
            continue
        module_path = match[1].replace("\\", "/")
        blob = subprocess.run([str(args.sevenzip), "x", "-so", str(path),
                               module_path], capture_output=True, check=True).stdout
        entry["modules"].append({"name": module_path, "bytes": len(blob),
                                 "sha256": hashlib.sha256(blob).hexdigest(),
                                 "modinfo": modinfo(blob)})
    report["images"].append(entry)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for entry in report["images"]:
    print(entry["file"], f'{len(entry["wireless_listing"])} wireless clue lines')
    for module in entry["modules"]:
        print(module["name"], "vermagic=", module["modinfo"].get("vermagic"),
              "aliases=", module["modinfo"].get("alias", []))
