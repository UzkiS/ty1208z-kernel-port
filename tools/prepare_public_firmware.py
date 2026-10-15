#!/usr/bin/env python3
"""Validate tracked RDA firmware and create the package preparer's input tree."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "rda5995_usb_code_p2p.bin", "rda5995_usb_code1_p2p.bin",
    "rda5995_usb_data_p2p.bin", "rda5995_usb_code_ap.bin",
    "rda5995_usb_data_ap.bin",
)

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
source = ROOT / "firmware/rda5995"
manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8-sig"))
args.output.mkdir(parents=True, exist_ok=True)
files = {}
for name in NAMES:
    data = (source / name).read_bytes()
    key = "vendor/firmware/" + name
    record = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    assert manifest["files"][key] == record, name
    (args.output / name).write_bytes(data)
    files[key] = record
(args.output / "manifest.json").write_text(json.dumps({
    "source": manifest["source"], "module_usb_alias": manifest["module_usb_alias"],
    "files": files,
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("PUBLIC_RDA_FIRMWARE_INPUT_PASS", len(files))
