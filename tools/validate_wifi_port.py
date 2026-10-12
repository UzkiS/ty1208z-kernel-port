#!/usr/bin/env python3
"""Verify the linked ARM module identity and excluded manufacturing symbols."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

root = Path(sys.argv[1])
module = (root / "rdawfmac-UNTESTED.ko").read_bytes()
assert module[:6] == b"\x7fELF\x01\x01"
assert struct.unpack_from("<HH", module, 16) == (1, 40), "Expected relocatable ARM ELF"
vermagic = re.findall(rb"(?:^|\0)vermagic=([^\0]+)\0", module)
assert len(vermagic) == 1 and vermagic[0].startswith(b"6.12.112-ty1208z-wifi-port ")
assert b"usb:v1E04p8888" in module
symbols = (root / "checks/symbols.txt").read_text()
assert not re.search(r"wland_(?:efuse_set_|write_efuse_|write_txpower_to_efuse|rf_test_cmd)", symbols)
config = (root / "linux.config").read_text()
for option in ("NET", "CFG80211", "USB", "MODULES", "FW_LOADER"):
    assert f"CONFIG_{option}=y\n" in config
assert "CONFIG_DEBUG_FS=y\n" not in config
manifest = {path.name: {"bytes": path.stat().st_size,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(root.iterdir()) if path.is_file() and path.name != "manifest.json"}
(root / "manifest.json").write_text(json.dumps({
    "status": "ARM module link only; hardware, firmware, STA/AP untested",
    "vermagic": vermagic[0].decode(), "files": manifest,
}, indent=2) + "\n")
print("RDA MODULE CHECK PASS: ARM relocatable ELF, exact release/USB alias, manufacturing symbols absent")
