#!/usr/bin/env python3
"""Structural checks only; these never establish hardware compatibility."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from inspect_images import inspect_image, parse_fdt
from emmc_profiles import identification_profile
from ethernet_profiles import ethernet_audit_profile, ethernet_clock_id_profile
from ethernet_net_profile import ethernet_net_profile
from usb_audit_profile import usb_audit_profile
from usb_clock_audit_profile import usb_clock_audit_profile
from usb_host_profile import usb_host_profile
from restart_profile import restart_profile
from sd_audit_profile import sd_audit_profile
from sd_ident_profile import sd_ident_profile

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
config = (artifacts / "linux.config").read_text()
audits = [node for node in tree["nodes"] if node["path"] == "/soc/emmc-audit@f9830000"]
if "CONFIG_HI3798MV100_EMMC_AUDIT=y\n" in config:
    assert len(audits) == 1
    assert audits[0]["properties"]["reg"]["cells"] == [0xf9830000, 0x1000, 0xf8a220a0, 4]
    assert "# CONFIG_MMC is not set\n" in config and "# CONFIG_BLOCK is not set\n" in config
else:
    assert not audits, "Audit node must only appear in the explicit audit profile"
identification_profile(tree, config)
sd_audit_profile(tree, config)
sd_ident_profile(tree, config)
ethernet_audit_profile(tree, config)
ethernet_clock_id_profile(tree, config)
ethernet_net_profile(tree, config)
usb_audit_profile(tree, config)
usb_clock_audit_profile(tree, config)
usb_host_profile(tree, config)
restart_profile(tree, config)
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
