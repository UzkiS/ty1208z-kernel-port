#!/usr/bin/env python3
"""Verify native Docker package provenance and ARM payloads; no daemon startup."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from prepare_openwrt import sha256

PROJECT = Path(__file__).resolve().parents[1]
PACKAGES = {"docker": ("29.6.1", "usr/bin/docker"),
            "dockerd": ("29.6.1", "usr/bin/dockerd"),
            "containerd": ("2.2.5", "usr/bin/containerd"),
            "runc": ("1.3.6", "usr/sbin/runc"),
            "tini": ("0.19.0", "usr/bin/tini")}


def unique(paths, label):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError(f"Expected exactly one {label}")
    return paths[0]


def check(source, built=False):
    marker = json.loads((source / ".ty1208z-container-compile-only.json").read_text())
    if marker != {"schema": 1,
                  "scope": "native Docker packages only; no rootfs/boot/runtime acceptance",
                  "config_sha256": sha256(PROJECT / "openwrt/containers/config")}:
        raise ValueError("Container package compile-only profile differs")
    config = (source / ".config").read_text()
    for option in ("TARGET_hi3798mv100_apps", "TARGET_hi3798mv100_apps_DEVICE_ty1208z_apps",
                   "USE_MUSL", "EXTERNAL_TOOLCHAIN", "KERNEL_SECCOMP", "KERNEL_SECCOMP_FILTER",
                   "KERNEL_NAMESPACES", "KERNEL_NET_NS", "KERNEL_CGROUPS", "KERNEL_MEMCG"):
        if f"CONFIG_{option}=y\n" not in config:
            raise ValueError(f"Missing container compile configuration: {option}")
    for package in PACKAGES:
        if f"CONFIG_PACKAGE_{package}=m\n" not in config:
            raise ValueError(f"Container package must remain compile-only: {package}")
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for relative, expected in manifest.items():
        if sha256(source / relative) != expected:
            raise ValueError(f"Changed container compilation input: {relative}")
    lock = json.loads((source / ".ty1208z-application-lock.json").read_text())
    for item in lock["feeds"]:
        if json.loads((source / "feeds" / item["name"] / ".ty1208z-feed.json").read_text()) != item:
            raise ValueError(f"Container feed identity differs: {item['name']}")
    recipes = {}
    recipe_lock = json.loads((PROJECT / "openwrt/containers/sources.lock.json").read_text())
    package_feed = next(item for item in lock["feeds"] if item["name"] == "packages")
    if recipe_lock["feed_commit"] != package_feed["commit"] or set(recipe_lock["packages"]) != set(PACKAGES):
        raise ValueError("Container recipes differ from the locked official feed")
    for name, (version, _) in PACKAGES.items():
        recipe = source / f"feeds/packages/utils/{name}/Makefile"
        text = recipe.read_text()
        if f"PKG_VERSION:={version}\n" not in text:
            raise ValueError(f"Container package version differs: {name}")
        digest = re.search(r"^PKG_HASH:=([0-9a-f]{64})$", text, re.MULTILINE)
        if digest is None:
            raise ValueError(f"Container package source is not hash-pinned: {name}")
        recipes[name] = {"version": version, "recipe_sha256": sha256(recipe),
                         "archive_sha256": digest.group(1)}
        if recipes[name] != recipe_lock["packages"][name]:
            raise ValueError(f"Container recipe differs from reviewed identity: {name}")
    if not built:
        print("OPENWRT_CONTAINER_CONFIG_PASS compile-only no-rootfs no-device-access")
        return
    kernel = unique((source / "build_dir").glob(
        "target-*/linux-hi3798mv100_apps/linux-6.12.112/.config"), "container dependency kernel")
    kernel_config = kernel.read_text()
    for option in ("MMC", "MTD", "USB_SUPPORT", "SMP", "HISI_FEMAC"):
        if re.search(rf"^CONFIG_{option}=[ym]$", kernel_config, re.MULTILINE):
            raise ValueError(f"Container compilation enables unreviewed board hardware: {option}")
    for option in ("BLOCK", "CGROUPS", "MEMCG", "NAMESPACES", "NET_NS", "SECCOMP", "SECCOMP_FILTER"):
        if f"CONFIG_{option}=y\n" not in kernel_config:
            raise ValueError(f"Container dependency kernel missing: {option}")
    if list((source / "bin/targets").rglob("*uImage*")) or list((source / "bin/targets").rglob("*rootfs*")):
        raise ValueError("Compile-only container entry emitted a boot image/rootfs")
    output = PROJECT / "artifacts/openwrt-container-packages"
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").unlink(missing_ok=True)
    apk = source / "staging_dir/host/bin/apk"
    go = source / "staging_dir/hostpkg/lib/go-1.26/bin/go"
    runtime_packages = {}
    for name, version in (("libc", "1.2.5"), ("libgcc1", "14.3.0"), ("libseccomp", "2.5.5")):
        paths = list((source / "bin/targets/hi3798mv100/apps/packages").glob(f"{name}-{version}-r*.apk"))
        paths += list((source / "bin/packages").glob(f"*/*/{name}-{version}-r*.apk"))
        package = unique(paths, name + " runtime APK")
        info = json.loads(subprocess.check_output([apk, "adbdump", "--format", "json", package], text=True))["info"]
        if (info["name"] != name or info["arch"] != "arm_cortex-a7_neon-vfpv4" or
                not re.fullmatch(re.escape(version) + r"-r\d+", info["version"])):
            raise ValueError(f"Actual runtime library APK identity differs: {name}")
        runtime_packages[name] = package
        shutil.copyfile(package, output / package.name)
    records = {}
    for name, (version, relative) in PACKAGES.items():
        package = unique((source / "bin/packages").glob(f"*/packages/{name}-{version}-r*.apk"), name + " APK")
        metadata = json.loads(subprocess.check_output([apk, "adbdump", "--format", "json", package], text=True))
        info = metadata["info"]
        if info["name"] != name or info["arch"] != "arm_cortex-a7_neon-vfpv4":
            raise ValueError(f"Actual container APK identity differs: {name}")
        if sha256(source / "dl" / f"{name}-{version}.tar.gz") != recipes[name]["archive_sha256"]:
            raise ValueError(f"Actual container source archive differs: {name}")
        with tempfile.TemporaryDirectory(prefix="ty1208z-container-apk-") as temporary:
            extracted = Path(temporary)
            # Compile-only package builds have no installed libc in the target
            # staging tree. Execute against actual ARM library APK payloads.
            for runtime in runtime_packages.values():
                subprocess.run([apk, "extract", "--allow-untrusted", "--no-chown", "--destination", extracted, runtime],
                               check=True, stdout=subprocess.PIPE)
            subprocess.run([apk, "extract", "--allow-untrusted", "--no-chown", "--destination", extracted, package],
                           check=True, stdout=subprocess.PIPE)
            binary = extracted / relative
            if not binary.is_file() or binary.is_symlink():
                raise ValueError(f"Actual APK lacks native executable: {relative}")
            staged = unique((source / "build_dir").glob(
                f"target-*/{name}-{version}/ipkg-*/{name}/{relative}"), name + " actual package staging executable")
            if staged.is_symlink() or sha256(staged) != sha256(binary):
                raise ValueError(f"Container APK differs from the actual package staging output: {name}")
            elf = subprocess.check_output(["readelf", "-h", "-A", binary], text=True)
            if "ELF32" not in elf or not re.search(r"Machine:\s+ARM\b", elf) or "Version5 EABI" not in elf:
                raise ValueError(f"Container APK executable is not ARM EABI5: {name}")
            version_output = subprocess.check_output(["qemu-arm", "-L", extracted, binary, "--version"],
                                                    stderr=subprocess.STDOUT, timeout=30).decode()
            if version not in version_output:
                raise ValueError(f"Actual ARM executable version differs: {name}")
            records[name] = {**recipes[name], "package_version": info["version"], "depends": info.get("depends", []),
                             "binary_sha256": sha256(binary), "version_output": version_output.strip()}
            if name != "tini":
                build_info = subprocess.check_output([go, "version", "-m", binary], text=True)
                if (not re.search(r"build\s+GOOS=linux$", build_info, re.MULTILINE) or
                        not re.search(r"build\s+GOARCH=arm$", build_info, re.MULTILINE) or
                        not re.search(r"build\s+GOARM=7(?:,hardfloat)?$", build_info, re.MULTILINE)):
                    raise ValueError(f"Actual container core is not compiled for ARMv7: {name}")
                records[name]["go_build_info_sha256"] = hashlib.sha256(build_info.encode()).hexdigest()
                records[name]["go_build_settings"] = {
                    key: re.search(rf"build\s+{key}=(.*)$", build_info, re.MULTILINE)[1]
                    for key in ("GOOS", "GOARCH", "GOARM", "CGO_ENABLED")}
        shutil.copyfile(package, output / package.name)
    for relative, filename in ((".config", "openwrt.config"),
                               (".ty1208z-application-lock.json", "application-sources.lock.json"),
                               (".ty1208z-toolchain.json", "toolchain.json")):
        shutil.copyfile(source / relative, output / filename)
    shutil.copyfile(PROJECT / "openwrt/containers/sources.lock.json", output / "container-sources.lock.json")
    shutil.copyfile(kernel, output / "linux.config")
    files = {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
             for path in sorted(output.iterdir()) if path.is_file()}
    (output / "manifest.json").write_text(json.dumps({
        "status": "native Docker packages and ARM version checks only; daemon/container/hardware untested",
        "packages": records, "files": files,
        "check_sources": {name: sha256(PROJECT / "tools" / name)
                          for name in ("check_openwrt_containers.py", "prepare_openwrt_applications.py",
                                       "build-openwrt-containers.sh")},
    }, indent=2) + "\n")
    print("OPENWRT_CONTAINER_PACKAGES_PASS actual-native-APK ARM-EABI5 versions; daemon/container untested")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--built", action="store_true")
    args = parser.parse_args()
    check(args.source.resolve(), args.built)


if __name__ == "__main__":
    main()
