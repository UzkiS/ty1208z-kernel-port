#!/usr/bin/env python3
"""Structural checks only; these never establish hardware compatibility."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from inspect_images import inspect_image, parse_fdt

artifacts = Path(sys.argv[1]).resolve()
evidence = artifacts / "checks"
evidence.mkdir(exist_ok=True)
image = inspect_image(artifacts / "uImage-UNTESTED.bin", evidence)
assert len(image["uimages"]) == 1
header = image["uimages"][0]
assert header["header_crc_valid"] and header["payload_crc_valid"]
assert header["load_address"] == "0x2000000" and header["entry_address"] == "0x2000000"
assert header["compression"] == 0
raw = (artifacts / "zImage").read_bytes()
assert struct.unpack_from("<I", raw, 0x24)[0] == 0x016f2818
assert len(raw) == struct.unpack_from("<I", raw, 0x2c)[0] - struct.unpack_from("<I", raw, 0x28)[0]
dtb = (artifacts / "ty1208z-diagnostic.dtb").read_bytes()
tree = parse_fdt(dtb)
assert tree["size"] == len(dtb)
uart = next(node["properties"] for node in tree["nodes"] if node["path"] == "/soc/serial@f8b00000")
assert "arm,primecell-periphid" not in uart, "Read the real UART ID; do not override with an unsupported ID"
assert (artifacts / "zImage-appended-dtb").read_bytes() == raw + dtb
assert (artifacts / "uImage-UNTESTED.bin").read_bytes()[64:] == raw + dtb
assert len(image["device_trees"]) == 1
assert image["device_trees"][0]["offset"] == 64 + len(raw)
assert image["bytes"] < 20 * 1024 * 1024, "Exceeds reference kernel slot size (no flash authorized)"
for name in ("busybox.armhf", "time64-probe.armhf"):
    elf = (artifacts / name).read_bytes()
    assert elf[:6] == b"\x7fELF\x01\x01"
    assert struct.unpack_from("<H", elf, 18)[0] == 40
(evidence / "image-validation.json").write_text(json.dumps(image, indent=2) + "\n")
manifest = {path.name: {"bytes": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(artifacts.iterdir()) if path.is_file() and path.name != "manifest.json"}
(artifacts / "manifest.json").write_text(json.dumps({"status": "offline structural checks only; hardware untested",
                                                   "files": manifest}, indent=2) + "\n")
print(f"Artifact checks passed: ARM uImage CRC, zImage header/length, appended DTB, ARM ELF; image={image['bytes']} bytes")
