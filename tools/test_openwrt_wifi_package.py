#!/usr/bin/env python3
"""Reject broken ABI, empty packages and activation hooks using a real built APK."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile

from check_openwrt_wifi import validate_payload

PROJECT = Path(__file__).resolve().parents[1]


def run(source):
    output = PROJECT / "artifacts/openwrt-wifi-port"
    manifest = json.loads((output / "manifest.json").read_text())
    metadata = json.loads((output / "checks/apk.json").read_text())
    module = output / "rdawfmac-link-UNTESTED.ko"
    config = (output / "linux.config").read_text()
    symbols = (output / "checks/symbols.txt").read_text()
    release, abi = manifest["kernel_release"], manifest["kernel_abi"]
    apk = source / "staging_dir/host/bin/apk"
    with tempfile.TemporaryDirectory(prefix="ty1208z-apk-regression-") as temporary:
        extracted = Path(temporary)
        subprocess.run([apk, "extract", "--allow-untrusted", "--no-chown", "--destination",
                        extracted, output / "kmod-ty1208z-rda-port-UNTESTED.apk"],
                       check=True, stdout=subprocess.PIPE)
        validate_payload(module, extracted, metadata, release, abi, config, symbols)
        rejected = []

        def reject(name, info=metadata, kernel_release=release, kernel_config=config):
            try:
                validate_payload(module, extracted, info, kernel_release, abi, kernel_config, symbols)
            except ValueError:
                rejected.append(name)
            else:
                raise AssertionError(f"Broken package accepted: {name}")

        reject("another kernel release", kernel_release=release + "-other")
        wrong_abi = copy.deepcopy(metadata)
        wrong_abi["info"]["depends"] = ["kernel=6.12.112~incorrect-r1"]
        reject("another kernel config ABI", info=wrong_abi)
        custom_hook = copy.deepcopy(metadata)
        custom_hook["scripts"]["post-install"] += "insmod /lib/modules/rdawfmac.ko\n"
        reject("automatic module-load install hook", info=custom_hook)
        reject("storage-enabled kernel", kernel_config=config + "\nCONFIG_USB_STORAGE=y\n")
        payload = extracted / f"lib/modules/{release}/rdawfmac.ko"
        original = payload.read_bytes()
        payload.unlink()
        reject("empty kmod APK")
        payload.write_bytes(original)
        for name, relative in (("unreviewed firmware", "lib/firmware/rda.bin"),
                               ("automatic module loading", "etc/modules.d/rdawfmac")):
            path = extracted / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"unexpected\n")
            reject(name)
            path.unlink()
        payload.write_bytes(original.replace(("vermagic=" + release).encode(),
                                             ("vermagic=" + "0" * len(release)).encode()))
        reject("stale packaged module release")
        payload.write_bytes(original)
        validate_payload(module, extracted, metadata, release, abi, config, symbols)
    (output / "checks/package-guards.json").write_text(json.dumps({
        "actual_apk": manifest["files"]["kmod-ty1208z-rda-port-UNTESTED.apk"]["sha256"],
        "rejected": rejected, "status": "host-only package guards; no installation or radio",
    }, indent=2) + "\n")
    print(f"OPENWRT_WIFI_PACKAGE_GUARDS_PASS: {len(rejected)} broken real-APK cases rejected")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    run(args.source)


if __name__ == "__main__":
    main()
