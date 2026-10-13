#!/usr/bin/env python3
"""Compile an exact native router RAM restart module, without loading it."""
import argparse
from pathlib import Path

from build_native_router_module import build_module, PROJECT

NAMES = ("ty1208z-sp805-restart.c", "ty1208z-sp805-restart.h", "ty1208z-mv100-restart.h")


def build(source, taskbase, artifacts):
    return build_module(source, taskbase, artifacts,
                        directory=("native-router-sdro-restart" if
                                   "CONFIG_TY1208Z_ROUTER_SD_RO=y\n" in (artifacts / "linux.config").read_text()
                                   else "native-router768-restart" if
                                   "CONFIG_TY1208Z_ROUTER_RAM768=y\n" in (artifacts / "linux.config").read_text()
                                   else "native-ram-restart"),
                        names=tuple("drivers/power/reset/" + name for name in NAMES),
                        module_name="ty1208z-sp805-restart", define="TY1208Z_RAM_RESTART_MODULE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--taskbase", type=Path, required=True)
    parser.add_argument("--router-artifacts", type=Path, default=PROJECT / "artifacts/openwrt-router1")
    args = parser.parse_args()
    build(args.source, args.taskbase, args.router_artifacts)
