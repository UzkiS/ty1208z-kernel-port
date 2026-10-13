#!/usr/bin/env python3
"""Compile the exact native router command-free SD register audit module."""
import argparse
from pathlib import Path

from build_native_router_module import build_module, PROJECT


def build(source, taskbase, artifacts):
    return build_module(source, taskbase, artifacts,
                        directory="native-ram-sd-audit",
                        names=("drivers/soc/hisilicon/hi3798mv100-sd-audit.c",),
                        module_name="hi3798mv100-sd-audit", define="TY1208Z_RAM_SD_AUDIT_MODULE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--taskbase", type=Path, required=True)
    parser.add_argument("--router-artifacts", type=Path, default=PROJECT / "artifacts/openwrt-router1")
    args = parser.parse_args()
    build(args.source, args.taskbase, args.router_artifacts)
