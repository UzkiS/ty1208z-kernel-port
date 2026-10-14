#!/usr/bin/env python3
"""Run real Kconfig mutations for the opt-in eMMC/network exception."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

from native_emmc_profile import native_emmc_configuration
from prepare_openwrt_applications import merge_kernel_fragment


def check(linuxsrc, config, cross_compile):
    original = config.read_text()
    protected = [linuxsrc / ".config", linuxsrc / "arch/arm/boot/zImage"]
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected if path.exists()}
    cases = {
        "native-emmc": ("", True, True, True),
        "unselected-emmc": ("# CONFIG_TY1208Z_ROUTER_EMMC_RO is not set\n", False, False, False),
        "missing-policy": ("# CONFIG_HI3798MV100_EMMC_READ_ONLY is not set\n", True, False, True),
        "missing-mmc": ("# CONFIG_MMC is not set\n", False, False, False),
        "missing-block": ("# CONFIG_BLOCK is not set\n", False, False, False),
        "missing-mac": ("# CONFIG_HISI_FEMAC is not set\n", False, False, False),
        "ordinary-network": ("# CONFIG_BLOCK is not set\n# CONFIG_MMC is not set\n"
                             "# CONFIG_TY1208Z_ROUTER_EMMC_RO is not set\n", False, False, True),
        "extra-partition-parser": ("CONFIG_OF_PARTITION=y\n", True, True, True),
        "block-throttling": ("CONFIG_CGROUPS=y\nCONFIG_BLK_CGROUP=y\nCONFIG_BLK_DEV_THROTTLING=y\n",
                             True, True, True),
    }
    for name, (fragment, native, policy, ethernet) in cases.items():
        with tempfile.TemporaryDirectory(prefix="native-emmc-kconfig-") as directory:
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
            assert (active.get("TY1208Z_ROUTER_EMMC_RO") == "y") == native, name
            assert (active.get("HI3798MV100_EMMC_READ_ONLY") == "y") == policy, name
            assert (active.get("TY1208Z_ETHERNET_INHERITED") == "y") == ethernet, name
            assert (active.get("FESTA_TY1208Z_PHY") == "y") == ethernet, name
            if name == "native-emmc":
                native_emmc_configuration(generated)
            if name in ("extra-partition-parser", "block-throttling"):
                option = "OF_PARTITION" if name == "extra-partition-parser" else "BLK_DEV_THROTTLING"
                assert active.get(option) == "y", name
                try:
                    native_emmc_configuration(generated)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Unreviewed native eMMC option accepted: " + option)
            print("NATIVE_EMMC_KCONFIG_CASE_PASS " + name, flush=True)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in hashes.items())
    print("NATIVE_EMMC_ACTUAL_KCONFIG_GATES_PASS opt-in eMMC/network, RO prerequisites and ordinary network preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linuxsrc", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cross-compile", default="arm-linux-gnueabihf-")
    args = parser.parse_args()
    check(args.linuxsrc, args.config, args.cross_compile)
