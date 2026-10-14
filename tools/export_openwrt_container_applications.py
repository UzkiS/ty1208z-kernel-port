#!/usr/bin/env python3
"""Export verified combined application QEMU evidence; never a board image."""
import argparse
import json
from pathlib import Path
import shutil

from prepare_openwrt import sha256
from prepare_openwrt_applications import application_variant
from test_openwrt_applications_qemu import identity, required_markers, unique

PROJECT = Path(__file__).resolve().parents[1]


def export(source):
    source = source.resolve()
    output = PROJECT / "artifacts/openwrt-container-applications-qemu"
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").unlink(missing_ok=True)
    if application_variant(source) != "container-qemu":
        raise ValueError("Combined delivery requires the independent QEMU-only profile")
    marker = json.loads((source / ".ty1208z-container-qemu-only.json").read_text())
    if marker != {"schema": 1,
                  "scope": "combined native applications and Docker for isolated QEMU only; no board image",
                  "config_sha256": sha256(PROJECT / "openwrt/containers/applications.config")}:
        raise ValueError("Combined delivery profile differs")
    images = source / "bin/targets/hi3798mv100/apps"
    checks = images / "checks"
    report_path = checks / "applications-qemu-768.json"
    report = json.loads(report_path.read_text())
    markers = required_markers("container-qemu")
    if (report["schema"] != 1 or report["application_variant"] != "container-qemu" or
            report["result"] != "OPENWRT_APPLICATIONS_QEMU_PASS" or
            report["machine"] != "virt,cortex-a7,single-core" or
            report["memory_mib"] != 768 or report["memory_limit_mib"] != 768 or
            report["clock_year"] != 2040 or report["host_network"] or report["disks"] or
            report["passed_markers"] != [marker.decode() for marker in markers]):
        raise ValueError("Combined QEMU acceptance scope differs")
    kernel = unique((source / "build_dir").glob(
        "target-*/linux-hi3798mv100_apps/linux-6.12.112/arch/arm/boot/zImage"), "combined kernel")
    native_initrd = unique(images.glob("*rootfs.cpio.gz"), "combined native initrd")
    native = {
        "kernel": kernel, "rootfs": native_initrd,
        "packages": unique(images.glob("*.manifest"), "combined package manifest"),
        "config": kernel.parents[3] / ".config",
        "feeds": source / ".ty1208z-application-lock.json",
        "toolchain": source / ".ty1208z-toolchain.json",
        "overlay": source / ".ty1208z-overlay.json",
        "openwrt_config": source / ".config",
        "container_profile": source / ".ty1208z-container-qemu-only.json",
    }
    artifacts = {"kernel": kernel, "rootfs": checks / "container-applications.QEMU-ONLY.cpio.gz",
                 "packages": native["packages"], "config": native["config"],
                 "console": checks / "qemu-applications-768.log"}
    inputs = {name: PROJECT / relative for name, relative in (
        ("test_harness", "tools/test_openwrt_applications_qemu.py"),
        ("ntp_server_source", "tools/ntp-qemu-fixture.c"),
        ("ntp_guest", "tools/openwrt-ntp-guest.sh"),
        ("applications_guest", "tools/openwrt-applications-guest.sh"),
        ("router_guest", "tools/openwrt-router-guest.sh"),
        ("qemu_wrapper", "tools/prepare_container_applications_qemu.py"),
        ("container_fixture_builder", "tools/test_openwrt_container_runtime.py"),
        ("initramfs_writer", "tools/make_initramfs.py"),
        ("container_configuration", "openwrt/containers/applications.config"),
        ("container_kernel_configuration", "openwrt/containers/applications-kernel.config"),
        ("container_resource_source", "tools/container-resource-probe.c"),
        ("container_helper_configuration", "config/busybox-container-qemu.fragment"),
        ("container_helper_base_configuration", "config/busybox-diagnostic.fragment"),
        ("container_helper_sources", "config/sources.lock.json"),
        ("container_helper_time64_patch", "patches/0002-busybox-stat-time64.patch"),
        ("qemu_stage", "initramfs/container-applications-qemu-init"),
        ("container_guest", "tools/openwrt-container-applications-guest.sh"),
    )}
    inputs.update(ntp_server_binary=checks / "ntp-qemu-fixture-768.armhf",
                  unzip_archive=checks / "unzip-fixture.zip", container_helper=checks / "busybox.armhf",
                  container_probe=checks / "container-resource-probe.armhf",
                  unmodified_native_initrd=native_initrd)
    for label, paths in (("native_inputs", native), ("artifacts", artifacts), ("test_inputs", inputs)):
        if {name: identity(path) for name, path in paths.items()} != report[label]:
            raise ValueError(f"Combined QEMU {label} differ from actual acceptance")
    console = artifacts["console"].read_bytes().replace(b"\r", b"")
    if (any(console.splitlines().count(marker) != 1 for marker in markers) or
            b"Kernel panic" in console or b"OPENWRT_APPLICATIONS_QEMU_FAIL" in console):
        raise ValueError("Combined console lacks complete one-time success")
    overlay = json.loads(native["overlay"].read_text())
    for relative, expected in overlay.items():
        if sha256(source / relative) != expected:
            raise ValueError(f"Combined native source changed: {relative}")
    board_patch = "target/linux/hi3798mv100/patches-6.12/0001-board-support.patch"
    if overlay[board_patch] != sha256(PROJECT / "patches/0001-hi3798mv100-diagnostic.patch"):
        raise ValueError("Combined native kernel must use the current reviewed board patch")
    packages_dir = PROJECT / "artifacts/openwrt-container-application-packages"
    package_report_path = packages_dir / "manifest.json"
    package_report = json.loads(package_report_path.read_text())
    if package_report["scope"] != marker["scope"]:
        raise ValueError("Combined native core package scope differs")
    for name, expected in package_report["files"].items():
        if Path(name).name != name or identity(packages_dir / name) != expected:
            raise ValueError(f"Combined native core package changed: {name}")
    for name, expected in package_report["check_sources"].items():
        if Path(name).name != name or sha256(PROJECT / "tools" / name) != expected:
            raise ValueError(f"Combined native core checker changed: {name}")
    for delivered, checked in (("linux.config", "config"), ("openwrt.config", "openwrt_config"),
                               ("application-sources.lock.json", "feeds"), ("toolchain.json", "toolchain")):
        if package_report["files"][delivered] != report["native_inputs"][checked]:
            raise ValueError("Combined native core and application provenance differ")
    files = {
        "zImage.QEMU-ONLY": kernel,
        "rootfs.native.QEMU-ONLY.cpio.gz": native_initrd,
        "rootfs.fixture.QEMU-ONLY.cpio.gz": artifacts["rootfs"],
        "linux.config": native["config"], "openwrt.config": native["openwrt_config"],
        "packages.manifest": native["packages"], "native-overlay.json": native["overlay"],
        "application-sources.lock.json": native["feeds"], "toolchain.json": native["toolchain"],
        "qemu-profile.json": native["container_profile"],
        "qemu.json": report_path, "qemu.log": artifacts["console"],
        "native-core-packages.json": package_report_path,
        "busybox.armhf": inputs["container_helper"], "container-resource-probe.armhf": inputs["container_probe"],
        "ntp-fixture.armhf": inputs["ntp_server_binary"], "unzip-fixture.zip": inputs["unzip_archive"],
    }
    expected = {name: identity(path) for name, path in files.items()}
    for name, path in files.items():
        shutil.copyfile(path, output / name)
        if identity(output / name) != expected[name] or identity(path) != expected[name]:
            raise ValueError(f"Combined delivery copy/source changed: {name}")
    (output / "manifest.json").write_text(json.dumps({
        "schema": 1, "status": "combined native applications and Docker passed isolated QEMU; physical untested",
        "scope": {"application_variant": "container-qemu", "memory_mib": 768,
                  "host_network": False, "disks": False, "host_mounts": False, "clock_year": 2040,
                  "board_image": False, "container_proxy_client": "native curl in actual container network namespace"},
        "native_board_patch_sha256": overlay[board_patch], "passed_markers": report["passed_markers"],
        "native_core_packages": package_report["packages"], "files": expected,
        "export_sources": {relative: sha256(PROJECT / relative) for relative in (
            "tools/export_openwrt_container_applications.py", "tools/build-openwrt-container-applications.sh")},
        "limits": "No physical Docker/storage/restart/Wi-Fi, external Internet/registry, IPv6 or performance acceptance",
    }, indent=2) + "\n")
    print("OPENWRT_CONTAINER_APPLICATIONS_EXPORT_PASS exact native/kernel/fixture/console; QEMU-only no-board-image")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    export(args.source)


if __name__ == "__main__":
    main()
