#!/usr/bin/env python3
"""Prepare isolated native RDA package inputs; no firmware, image or hardware."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess

from fetch_wifi import load_lock, source_entries, verify
from prepare_openwrt import prepare, sha256, toolchain_from_native
from prepare_openwrt_applications import merge_kernel_fragment


def prepare_wifi(project, taskbase):
    toolchain, identity = toolchain_from_native(project, taskbase)
    wifi_base = taskbase / "openwrt-wifi-port"
    wifi_base.mkdir(parents=True, exist_ok=True)
    downloads = wifi_base / "downloads"
    if not downloads.exists():
        downloads.symlink_to(taskbase / "downloads", target_is_directory=True)
    if downloads.resolve() != (taskbase / "downloads").resolve():
        raise ValueError("Wi-Fi download cache differs from the fixed taskbase")
    with redirect_stdout(io.StringIO()):
        source = prepare(project, wifi_base)
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for path in sorted((project / "openwrt/wifi-port/overlay").rglob("*")):
        if path.is_file():
            relative = path.relative_to(project / "openwrt/wifi-port/overlay")
            output = source / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)
            manifest[str(relative)] = sha256(output)
    relative = "target/linux/hi3798mv100/config-6.12"
    fragment = (project / "openwrt/wifi-port/kernel.config").read_text()
    (source / relative).write_text(merge_kernel_fragment((source / relative).read_text(), fragment))
    manifest[relative] = sha256(source / relative)
    lock = load_lock(project / "reference/wifi-rda-usb.lock.json")
    pristine = taskbase / "rda-usb/source"
    subprocess.run(["python3", str(project / "tools/fetch_wifi.py"), "--output", str(pristine)],
                   check=True, stdout=subprocess.PIPE)
    for generator, name in (("make_wifi_usb_patch.py", "0003-rda-usb-api-audit.patch"),
                            ("make_wifi_port_patch.py", "0004-rda-linux-6.12-port.patch")):
        subprocess.run(["python3", str(project / "tools" / generator), "--source", str(pristine),
                        "--output", str(project / "patches" / name)], check=True, stdout=subprocess.PIPE)
    inputs = source / "ty1208z-rda-inputs"
    expected_sources = {item["path"] for item in source_entries(lock)}
    if inputs.exists():
        allowed = {"Kbuild", "sources.lock.json"} | {"source/" + name for name in expected_sources}
        for path in inputs.rglob("*"):
            if path.is_symlink() or (path.is_file() and str(path.relative_to(inputs)) not in allowed):
                raise ValueError(f"Unexpected cached Wi-Fi input: {path.relative_to(inputs)}")
    input_files = {}
    for item in source_entries(lock):
        data = (pristine / item["path"]).read_bytes()
        verify(item, data)
        output = inputs / "source" / item["path"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        input_files[str(output.relative_to(source))] = sha256(output)
    for original, output in (
            (project / "wifi/Kbuild", inputs / "Kbuild"),
            (project / "reference/wifi-rda-usb.lock.json", inputs / "sources.lock.json"),
            (project / "patches/0003-rda-usb-api-audit.patch",
             source / "package/kernel/ty1208z-rda-port/patches/0003-usb-api.patch"),
            (project / "patches/0004-rda-linux-6.12-port.patch",
             source / "package/kernel/ty1208z-rda-port/patches/0004-port.patch")):
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, output)
        input_files[str(output.relative_to(source))] = sha256(output)
    (source / ".ty1208z-overlay.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (source / ".ty1208z-wifi-inputs.json").write_text(json.dumps(input_files, indent=2) + "\n")
    (source / ".ty1208z-toolchain.json").write_text(json.dumps(identity, indent=2) + "\n")
    config = (project / "openwrt/config/ram.config").read_text()
    config += (project / "openwrt/wifi-port/config").read_text()
    config += ("CONFIG_EXTERNAL_TOOLCHAIN=y\n"
               f"CONFIG_TOOLCHAIN_ROOT={json.dumps(str(toolchain))}\n"
               'CONFIG_TARGET_NAME="arm-openwrt-linux-muslgnueabi"\n'
               'CONFIG_TOOLCHAIN_PREFIX="arm-openwrt-linux-muslgnueabi-"\n'
               'CONFIG_EXTERNAL_GCC_VERSION="14.3.0"\n'
               "CONFIG_EXTERNAL_TOOLCHAIN_LIBC_USE_MUSL=y\n")
    (source / ".config").write_text(config)
    print(source)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taskbase", type=Path, required=True)
    args = parser.parse_args()
    prepare_wifi(Path(__file__).resolve().parents[1], args.taskbase.resolve())


if __name__ == "__main__":
    main()
