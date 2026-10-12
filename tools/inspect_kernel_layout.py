#!/usr/bin/env python3
"""Tie the decompression footprint to the built zImage and ARM System.map."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    symbols = {}
    for line in (args.build / "System.map").read_text().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in {"_text", "_edata", "_end"}:
            symbols[fields[2]] = int(fields[0], 16)
    image = (args.build / "arch/arm/boot/Image").read_bytes()
    compressed = (args.build / "arch/arm/boot/compressed/piggy_data").read_bytes()
    zimage = (args.build / "arch/arm/boot/zImage").read_bytes()
    if gzip.decompress(compressed) != image or zimage.find(compressed) < 0:
        raise ValueError("Compressed data does not match the built Image/zImage")
    if symbols.get("_text") != 0xC0008000 or symbols["_edata"] - symbols["_text"] != len(image):
        raise ValueError("Unexpected ARM diagnostic kernel virtual layout")
    if not symbols["_edata"] <= symbols["_end"] < 0xC1000000:
        raise ValueError("Diagnostic kernel footprint exceeds the low 16 MiB bound")
    report = {
        "schema": 1, "status": "built image footprint; not hardware execution",
        "zimage_sha256": hashlib.sha256(zimage).hexdigest(),
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "physical_start": symbols["_text"] - 0xC0000000,
        "physical_image_end": symbols["_edata"] - 0xC0000000,
        "physical_bss_end": symbols["_end"] - 0xC0000000,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Kernel footprint: 0x{report['physical_start']:x}..0x{report['physical_bss_end']:x}; zImage verified")


if __name__ == "__main__":
    main()
