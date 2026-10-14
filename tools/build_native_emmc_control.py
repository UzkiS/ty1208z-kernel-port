#!/usr/bin/env python3
"""Build a fixed-device ARM RAM helper; no host or card block-device access."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from prepare_openwrt import toolchain_from_native

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taskbase", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    args.output.mkdir(parents=True)
    toolchain, identity = toolchain_from_native(ROOT, args.taskbase)
    source = ROOT / "openwrt/system/persistent/emmc-p9-control.c"
    binary = args.output / "emmc-p9-control.arm"
    subprocess.run([str(toolchain / "bin/arm-openwrt-linux-muslgnueabi-gcc"), "-static", "-Os",
                    "-Wall", "-Wextra", "-Werror", "-s", str(source), "-o", str(binary)], check=True)
    receipt = {"status": "compiled RAM-only p9 ioctl helper; not physically run", "compiler": identity,
               "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "file": binary.name, "bytes": binary.stat().st_size,
               "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "hardware_actions": False}
    (args.output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "sha256": receipt["sha256"]}))


if __name__ == "__main__":
    main()
