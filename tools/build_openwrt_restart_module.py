#!/usr/bin/env python3
"""Compile an exact native router RAM restart module, without loading it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from prepare_openwrt import toolchain_from_native
from ethernet_net_profile import openwrt_router_ethernet_profile
from inspect_images import parse_fdt

PROJECT = Path(__file__).resolve().parents[1]
NAMES = ("ty1208z-sp805-restart.c", "ty1208z-sp805-restart.h", "ty1208z-mv100-restart.h")


def build(source, taskbase, artifacts):
    source, taskbase, artifacts = source.resolve(), taskbase.resolve(), artifacts.resolve()
    output = PROJECT / "artifacts/native-ram-restart"
    record = output / "manifest.json"
    record.unlink(missing_ok=True)
    config = (artifacts / "linux.config").read_bytes()
    tree = parse_fdt((artifacts / "ty1208z-diagnostic.dtb").read_bytes())
    if not openwrt_router_ethernet_profile(tree, config.decode()):
        raise ValueError("The actual router artifacts must pass their exact board profile")
    kernels = list(source.glob("build_dir/target-*/linux-hi3798mv100_apps/linux-6.12.112"))
    if len(kernels) != 1:
        raise ValueError("Expected one completed native router kernel")
    kernel, = kernels
    zimage = (artifacts / "zImage").read_bytes()
    if ((kernel / ".config").read_bytes() != config or
            (kernel / "arch/arm/boot/zImage").read_bytes() != zimage or
            not (kernel / "Module.symvers").is_file()):
        raise ValueError("Kernel configuration/image/symbols must match the delivered router")
    toolchain, identity = toolchain_from_native(PROJECT, taskbase)
    if identity != json.loads((source / ".ty1208z-toolchain.json").read_text()):
        raise ValueError("Native compiler/libc differs from the router toolchain record")
    compiler = toolchain / "bin/arm-openwrt-linux-muslgnueabi-gcc"
    if compiler.read_bytes()[:4] != b"\x7fELF":
        raise ValueError("Modules require the actual compiler, not a userspace include wrapper")
    work = taskbase / "build/native-ram-restart"
    work.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        shutil.copyfile(PROJECT / "overlay/drivers/power/reset" / name, work / name)
    (work / "Makefile").write_text("obj-m := ty1208z-sp805-restart.o\n"
                                  "ccflags-y := -DTY1208Z_RAM_RESTART_MODULE\n")
    subprocess.run(["make", "-C", str(kernel), "M=" + str(work), "ARCH=arm",
                    "CROSS_COMPILE=" + str(compiler).removesuffix("gcc"), "-j4", "modules"], check=True)
    module = work / "ty1208z-sp805-restart.ko"
    data = module.read_bytes()
    if (data[:6] != b"\x7fELF\x01\x01" or data[18:20] != b"\x28\x00" or
            b"vermagic=6.12.112 " not in data or b"license=GPL" not in data):
        raise ValueError("Wrong module architecture/version/license")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(module, output / module.name)
    result = {"module": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
              "kernel_config_sha256": hashlib.sha256(config).hexdigest(),
              "zimage_sha256": hashlib.sha256(zimage).hexdigest(), "toolchain": identity,
              "sources": {name: hashlib.sha256((work / name).read_bytes()).hexdigest() for name in NAMES},
              "scope": "Exact native router external module; no physical load or restart"}
    record.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--taskbase", type=Path, required=True)
    parser.add_argument("--router-artifacts", type=Path, default=PROJECT / "artifacts/openwrt-router1")
    args = parser.parse_args()
    build(args.source, args.taskbase, args.router_artifacts)
