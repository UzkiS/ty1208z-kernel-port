#!/usr/bin/env python3
"""Verify native RDA inputs, real kernel linkage and the extracted APK payload."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from fetch_wifi import load_lock, source_entries, verify
from prepare_openwrt import sha256

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = "package/kernel/ty1208z-rda-port"


def enabled(config, options):
    for option in options:
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"Missing native Wi-Fi option: {option}")


def disabled(config, options):
    for option in options:
        if re.search(rf"^CONFIG_{re.escape(option)}=[ym]$", config, re.M):
            raise ValueError(f"Unexpected native Wi-Fi subsystem: {option}")


def check_inputs(source):
    lock = json.loads((PROJECT / "openwrt/sources.lock.json").read_text())
    if json.loads((source / ".ty1208z-source.json").read_text()) != lock["openwrt"]:
        raise ValueError("Native Wi-Fi tree does not match the pinned OpenWrt source")
    config = (source / ".config").read_text()
    enabled(config, ("TARGET_hi3798mv100", "TARGET_hi3798mv100_ram",
                     "TARGET_hi3798mv100_ram_DEVICE_ty1208z_ca_ram", "USE_MUSL",
                     "EXTERNAL_TOOLCHAIN", "PACKAGE_kmod-ty1208z-rda-port", "KERNEL_KALLSYMS"))
    disabled(config, ("PACKAGE_kmod-cfg80211", "PACKAGE_kmod-mac80211",
                      "TARGET_hi3798mv100_net", "KERNEL_DEBUG_FS", "KERNEL_SMP",
                      "KERNEL_PROFILING", "NO_STRIP"))
    if (source / "feeds.conf").read_text() != "# RAM bring-up: no external feeds.\n":
        raise ValueError("Wi-Fi compile tree unexpectedly uses application feeds")
    identity = json.loads((source / ".ty1208z-toolchain.json").read_text())
    if identity["gcc"] != "14.3.0" or identity["machine"] != "arm-openwrt-linux-muslgnueabi":
        raise ValueError("Wrong native Wi-Fi compiler identity")
    compiler_root = re.search(r'^CONFIG_TOOLCHAIN_ROOT="([^"\n]+)"$', config, re.M)
    if not compiler_root:
        raise ValueError("Missing actual external compiler path")
    toolchain = Path(compiler_root[1])
    for relative, key in (("bin/arm-openwrt-linux-muslgnueabi-gcc", "compiler_sha256"),
                          ("lib/libc.so", "libc_sha256")):
        if sha256(toolchain / relative) != identity[key]:
            raise ValueError(f"Changed actual native compiler/libc: {relative}")
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for relative, expected in manifest.items():
        if sha256(source / relative) != expected:
            raise ValueError(f"Changed native target input: {relative}")
    package = source / PACKAGE
    expected_recipe = PROJECT / "openwrt/wifi-port/overlay" / PACKAGE / "Makefile"
    if (package / "Makefile").read_bytes() != expected_recipe.read_bytes():
        raise ValueError("Package recipe differs from the reviewed optional overlay")
    inputs = source / "ty1208z-rda-inputs"
    lock = load_lock(PROJECT / "reference/wifi-rda-usb.lock.json")
    expected_paths = {"Kbuild", "sources.lock.json"}
    for item in source_entries(lock):
        relative = "source/" + item["path"]
        expected_paths.add(relative)
        verify(item, (inputs / relative).read_bytes())
    actual_paths = set()
    for path in inputs.rglob("*"):
        if path.is_symlink():
            raise ValueError("Wi-Fi source inputs must not contain symlinks")
        if path.is_file():
            actual_paths.add(str(path.relative_to(inputs)))
    if actual_paths != expected_paths:
        raise ValueError(f"Unpinned or missing Wi-Fi input: {actual_paths ^ expected_paths}")
    copies = ((PROJECT / "wifi/Kbuild", inputs / "Kbuild"),
              (PROJECT / "reference/wifi-rda-usb.lock.json", inputs / "sources.lock.json"),
              (PROJECT / "patches/0003-rda-usb-api-audit.patch", package / "patches/0003-usb-api.patch"),
              (PROJECT / "patches/0004-rda-linux-6.12-port.patch", package / "patches/0004-port.patch"))
    for original, copied in copies:
        if original.read_bytes() != copied.read_bytes():
            raise ValueError(f"Changed native RDA build input: {copied.name}")
    recorded = json.loads((source / ".ty1208z-wifi-inputs.json").read_text())
    paths = {"ty1208z-rda-inputs/" + name for name in expected_paths}
    paths |= {str(copied.relative_to(source)) for _, copied in copies}
    if set(recorded) != paths or any(sha256(source / name) != recorded[name] for name in paths):
        raise ValueError("Native RDA provenance is incomplete or stale")
    return identity, toolchain


def validate_payload(module, packaged, package_info, release, abi, config, symbols):
    data = module.read_bytes()
    if data[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<HH", data, 16) != (1, 40):
        raise ValueError("Native RDA module is not relocatable little-endian ARM ELF")
    vermagic = re.findall(rb"(?:^|\0)vermagic=([^\0]+)\0", data)
    if len(vermagic) != 1 or not vermagic[0].startswith((release + " ").encode()):
        raise ValueError("RDA vermagic does not match the actual native kernel")
    if b"usb:v1E04p8888" not in data:
        raise ValueError("Native RDA module lacks the locked USB alias")
    if re.search(r"wland_(?:efuse_set_|write_efuse_|write_txpower_to_efuse|rf_test_cmd)", symbols):
        raise ValueError("Manufacturing eFuse-write symbol survives")
    enabled(config, ("ARCH_HI3798MV100", "HI3798MV100_TIMER", "NET", "CFG80211",
                     "USB", "MODULES", "FW_LOADER", "WIRELESS",
                     "CFG80211_REQUIRE_SIGNED_REGDB", "CFG80211_USE_KERNEL_REGDB_KEYS", "WERROR"))
    disabled(config, ("DEBUG_FS", "USB_EHCI_HCD", "USB_OHCI_HCD", "USB_XHCI_HCD",
                      "USB_STORAGE", "MMC", "MTD", "BLOCK", "SMP", "NL80211_TESTMODE",
                      "MODULE_STRIPPED"))
    info = package_info["info"]
    if info["name"] != "kmod-ty1208z-rda-port":
        raise ValueError("Wrong actual APK package")
    dependencies = info.get("depends", [])
    if f"kernel={abi}" not in dependencies:
        raise ValueError(f"APK lacks exact native kernel ABI dependency: {dependencies}")
    files = {str(path.relative_to(packaged)) for path in packaged.rglob("*") if path.is_file()}
    expected = f"lib/modules/{release}/rdawfmac.ko"
    inventory = "lib/apk/packages/kmod-ty1208z-rda-port.list"
    if files != {expected, inventory} or any(path.is_symlink() for path in packaged.rglob("*")):
        raise ValueError(f"Unexpected APK payload (firmware/autoload/hooks forbidden): {files}")
    if (packaged / inventory).read_text() != "/" + expected + "\n":
        raise ValueError("Wrong actual APK file inventory")
    common = ('[ -s ${IPKG_INSTROOT}/lib/functions.sh ] || exit 0\n'
              '. ${IPKG_INSTROOT}/lib/functions.sh\n'
              'export root="${IPKG_INSTROOT}"\n'
              'export pkgname="kmod-ty1208z-rda-port"\n')
    post = ('[ "${IPKG_NO_SCRIPT}" = "1" ] && exit 0\n' + common +
            'add_group_and_user\ndefault_postinst\n')
    expected_scripts = {"post-install": "#!/bin/sh\n" + post,
                        "post-upgrade": "#!/bin/sh\nexport PKG_UPGRADE=1\n" + post,
                        "pre-deinstall": "#!/bin/sh\n" + common + "default_prerm\n"}
    if package_info.get("scripts") != expected_scripts:
        raise ValueError("APK contains unexpected hooks beyond the standard OpenWrt wrappers")
    # OpenWrt strips modules before packaging. Compare against its installed
    # module, not the unstripped linker output.
    packaged_module = packaged / expected
    if not packaged_module.read_bytes().startswith(b"\x7fELF\x01\x01"):
        raise ValueError("APK module is empty or not ARM ELF")
    packaged_vermagic = re.findall(rb"(?:^|\0)vermagic=([^\0]+)\0", packaged_module.read_bytes())
    if packaged_vermagic != vermagic:
        raise ValueError("Packaged module has a different vermagic")
    return vermagic[0].decode(), packaged_module


def check(source, built=False):
    identity, toolchain = check_inputs(source)
    if not built:
        print("OPENWRT_WIFI_CONFIG_PASS")
        return
    kernels = list((source / "build_dir").glob("target-*/linux-hi3798mv100_ram/linux-6.12.112"))
    modules = list((source / "build_dir").glob("target-*/linux-hi3798mv100_ram/ty1208z-rda-port-*/rdawlan/rdawfmac.ko"))
    packages = list((source / "bin").rglob("kmod-ty1208z-rda-port-*.apk"))
    if len(kernels) != 1 or len(modules) != 1 or len(packages) != 1:
        raise ValueError(f"Expected one native kernel/module/APK, got {len(kernels)}/{len(modules)}/{len(packages)}")
    kernel, module, package = kernels[0], modules[0], packages[0]
    release = re.fullmatch(r'#define UTS_RELEASE "([^"\n]+)"\n',
                           (kernel / "include/generated/utsrelease.h").read_text())[1]
    abi_hash = (kernel / ".vermagic").read_text().strip()
    abi = "6.12.112~" + abi_hash + "-r1"
    config = (kernel / ".config").read_text()
    prefix = str(toolchain / "bin/arm-openwrt-linux-muslgnueabi-")
    symbols = subprocess.check_output([prefix + "nm", str(module)], text=True)
    undefined = subprocess.check_output([prefix + "nm", "-u", str(module)], text=True)
    imports = {line.split()[-1] for line in undefined.splitlines() if line.strip()}
    exports = {line.split()[1]: line.split()[2]
               for line in (kernel / "Module.symvers").read_text().splitlines()}
    missing = imports - exports.keys()
    if not imports or missing:
        raise ValueError(f"RDA imports absent from the actual native kernel: {missing}")
    providers = {name: exports[name] for name in imports if exports[name] != "vmlinux"}
    if providers:
        raise ValueError(f"RDA needs additional unrepresented kernel-module dependencies: {providers}")
    apk = source / "staging_dir/host/bin/apk"
    metadata = json.loads(subprocess.check_output([apk, "adbdump", "--format", "json", package], text=True))
    output = PROJECT / "artifacts/openwrt-wifi-port"
    checks = output / "checks"
    checks.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ty1208z-apk-check-") as temporary:
        extracted = Path(temporary)
        subprocess.run([apk, "extract", "--allow-untrusted", "--no-chown", "--destination",
                        extracted, package], check=True, stdout=subprocess.PIPE)
        vermagic, payload = validate_payload(module, extracted, metadata, release, abi, config, symbols)
        # Equality to the package staging module detects stale APKs after a rebuild.
        staged = (module.parent.parent / ("ipkg-" + metadata["info"]["arch"]) /
                  "kmod-ty1208z-rda-port" / payload.relative_to(extracted))
        if staged.read_bytes() != payload.read_bytes():
            raise ValueError("APK module differs from the actual package staging output")
        stripped = extracted / "linked-module.ko"
        shutil.copyfile(module, stripped)
        strip_env = os.environ.copy()
        strip_env["CROSS"] = prefix
        for variable in ("KEEP_SYMBOLS", "KEEP_BUILD_ID", "NO_RENAME"):
            strip_env.pop(variable, None)
        # rules.mk preserves names when this profile enables KERNEL_KALLSYMS.
        strip_env["NO_RENAME"] = "1"
        subprocess.run(["sh", source / "scripts/strip-kmod.sh", stripped], env=strip_env, check=True)
        if stripped.read_bytes() != payload.read_bytes():
            raise ValueError("APK payload is not the stripped output of the actual linked RDA module")
        shutil.copyfile(payload, output / "rdawfmac-packaged-UNTESTED.ko")
    (checks / "apk.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (checks / "symbols.txt").write_text(symbols)
    (checks / "imports.json").write_text(json.dumps(sorted(imports), indent=2) + "\n")
    for original, name in ((module, "rdawfmac-link-UNTESTED.ko"), (package, "kmod-ty1208z-rda-port-UNTESTED.apk"),
                            (kernel / ".config", "linux.config"), (source / ".config", "openwrt.config"),
                            (source / ".ty1208z-wifi-inputs.json", "inputs.json"),
                            (kernel / "Module.symvers", "Module.symvers"),
                            (PROJECT / "wifi/Kbuild", "Kbuild"),
                            (PROJECT / "reference/wifi-rda-usb.lock.json", "wifi-sources.lock.json"),
                            (PROJECT / "openwrt/sources.lock.json", "openwrt-sources.lock.json"),
                            (PROJECT / "openwrt/wifi-port/overlay" / PACKAGE / "Makefile", "package.Makefile"),
                            (PROJECT / "patches/0003-rda-usb-api-audit.patch", "0003-usb-api.patch"),
                            (PROJECT / "patches/0004-rda-linux-6.12-port.patch", "0004-port.patch")):
        shutil.copyfile(original, output / name)
    files = {str(path.relative_to(output)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
             for path in sorted(output.rglob("*")) if path.is_file() and path.name != "manifest.json"}
    (output / "manifest.json").write_text(json.dumps({
        "status": "native OpenWrt compile/package only; no boot image; hardware/firmware/radio untested",
        "kernel_release": release, "kernel_abi": abi, "vermagic": vermagic,
        "toolchain": identity, "cfg80211": "native Linux 6.12 built-in; no OpenWrt backports",
        "check_sources": {name: sha256(PROJECT / "tools" / name)
                          for name in ("check_openwrt_wifi.py", "test_openwrt_wifi_package.py",
                                       "make_wifi_port_patch.py", "prepare_openwrt_wifi.py")},
        "files": files,
    }, indent=2) + "\n")
    print(f"OPENWRT_WIFI_PACKAGE_PASS: {release}; exact kernel ABI; no autoload/firmware")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--built", action="store_true")
    args = parser.parse_args()
    check(args.source, args.built)


if __name__ == "__main__":
    main()
