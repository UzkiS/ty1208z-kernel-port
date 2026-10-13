#!/usr/bin/env python3
"""Execute actual Kconfig dependency gates for native SD, Ethernet and init retention."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

from native_sd_profile import native_sd_configuration
from prepare_openwrt_applications import merge_kernel_fragment


def check(linuxsrc, config, cross_compile="arm-linux-gnueabihf-"):
    original = config.read_text()
    # Protect an in-tree native build: every mutation uses its own config.
    protected = [linuxsrc / ".config", linuxsrc / "arch/arm/boot/zImage"]
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected if path.exists()}
    cases = {
        "native-sd": ("", True, True),
        "unselected-sd": ("# CONFIG_TY1208Z_ROUTER_SD_RO is not set\n", False, False),
        "missing-read-only": ("# CONFIG_HI3798MV100_SD_READ_ONLY is not set\n", False, False),
        "missing-mmc": ("# CONFIG_MMC is not set\n", False, False),
        "missing-block": ("# CONFIG_BLOCK is not set\n", False, False),
        "missing-mac": ("# CONFIG_HISI_FEMAC is not set\n", False, False),
        "ordinary-network": ("# CONFIG_BLOCK is not set\n# CONFIG_MMC is not set\n"
                             "# CONFIG_TY1208Z_ROUTER_SD_RO is not set\n", False, True),
    }
    for name, (fragment, sd, ethernet) in cases.items():
        with tempfile.TemporaryDirectory(prefix="native-sd-kconfig-") as directory:
            output = Path(directory)
            candidate = output / ".config"
            candidate.write_text(merge_kernel_fragment(original, fragment))
            arguments = ["make", "-s", "-C", str(linuxsrc), "ARCH=arm", "CROSS_COMPILE=" + cross_compile,
                         "KCONFIG_CONFIG=" + str(candidate)]
            if not (linuxsrc / ".config").exists():
                arguments.append("O=" + str(output))
            result = subprocess.run(arguments + ["olddefconfig"], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=120)
            assert result.returncode == 0, result.stdout + result.stderr
            generated = candidate.read_text()
            active = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", generated, re.MULTILINE))
            assert (active.get("TY1208Z_ROUTER_SD_RO") == "y") == sd, name
            assert (active.get("TY1208Z_ETHERNET_INHERITED") == "y") == ethernet, name
            assert (active.get("FESTA_TY1208Z_PHY") == "y") == ethernet, name
            if sd:
                native_sd_configuration(generated)
            print("NATIVE_SD_KCONFIG_CASE_PASS " + name, flush=True)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in hashes.items())
    print("NATIVE_SD_ACTUAL_KCONFIG_GATES_PASS dedicated SD-only exception, RO prerequisites and ordinary network preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linuxsrc", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cross-compile", default="arm-linux-gnueabihf-")
    args = parser.parse_args()
    check(args.linuxsrc, args.config, args.cross_compile)
