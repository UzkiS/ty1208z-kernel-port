#!/usr/bin/env python3
"""Prepare an isolated native Ethernet RAM target without application feeds."""
import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

from prepare_openwrt import prepare, sha256, toolchain_from_native


def prepare_ethernet(project, taskbase):
    toolchain, identity = toolchain_from_native(project, taskbase)
    netbase = taskbase / "ethernet"
    netbase.mkdir(parents=True, exist_ok=True)
    downloads = netbase / "downloads"
    if not downloads.exists():
        downloads.symlink_to(taskbase / "downloads", target_is_directory=True)
    if downloads.resolve() != (taskbase / "downloads").resolve():
        raise ValueError("Ethernet download cache differs")
    with redirect_stdout(io.StringIO()):
        source = prepare(project, netbase)
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for path in sorted((project / "openwrt/ethernet/overlay").rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project / "openwrt/ethernet/overlay")
        output = source / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)
        manifest[str(relative)] = sha256(output)
    for relative, anchor, replacement in (
        ("target/linux/hi3798mv100/Makefile", "SUBTARGETS:=ram\n", "SUBTARGETS:=ram net\n"),
        ("target/linux/hi3798mv100/image/Makefile", "include $(INCLUDE_DIR)/image.mk\n",
         "include $(INCLUDE_DIR)/image.mk\n\nifeq ($(SUBTARGET),net)\n"
         "include $(TOPDIR)/target/linux/hi3798mv100/net/image.mk\nelse\n"),
        # Linux rejects the 'modules' make goal when CONFIG_MODULES=n. This
        # isolated experiment builds the same kernel goal without that goal;
        # neither the native core nor the apps tree is modified.
        ("include/kernel-defaults.mk",
         "\t+$(KERNEL_MAKE) $(if $(KERNELNAME),$(KERNELNAME),all) modules\n",
         "\t+$(KERNEL_MAKE) $(if $(KERNELNAME),$(KERNELNAME),all)\n"),
        # Upstream's hidden IPV6 def_bool ignores '.config ... is not set'.
        # Keep the first board experiment IPv4-only in this isolated tree.
        ("config/Config-build.in", "\tconfig IPV6\n\t\tdef_bool y\n",
         "\tconfig IPV6\n\t\tdef_bool n\n"),
    ):
        path = source / relative
        content = path.read_text()
        if relative in ("include/kernel-defaults.mk", "config/Config-build.in") and replacement in content and anchor not in content:
            manifest[relative] = sha256(path)
            continue
        if content.count(anchor) != 1:
            raise ValueError(f"Changed native recipe anchor: {relative}")
        content = content.replace(anchor, replacement)
        if relative.endswith("image/Makefile"):
            content += "endif\n"
        path.write_text(content)
        manifest[relative] = sha256(path)
    lock = json.loads((project / "openwrt/ethernet/sources.lock.json").read_text())
    recipe = lock["recipe_source"]
    archive = downloads / recipe["archive"]
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + ".partial")
        urllib.request.urlretrieve(recipe["url"], partial)
        if sha256(partial) != recipe["sha256"]:
            raise ValueError("Downloaded recipe archive hash differs")
        partial.replace(archive)
    if sha256(archive) != recipe["sha256"]:
        raise ValueError("Recipe archive hash differs")
    with tarfile.open(archive) as packed:
        member = packed.getmember(recipe["member"])
        if not member.isfile():
            raise ValueError("Expected a regular recipe file")
        content = packed.extractfile(member).read()
    if hashlib.sha256(content).hexdigest() != recipe["member_sha256"]:
        raise ValueError("Pinned iperf3 recipe hash differs")
    if (f"PKG_VERSION:={lock['iperf3']['version']}\n".encode() not in content or
            f"PKG_HASH:={lock['iperf3']['sha256']}\n".encode() not in content):
        raise ValueError("iperf3 source identity differs from its recipe")
    relative = "package/ty1208z-iperf3/Makefile"
    output = source / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    manifest[relative] = sha256(output)
    (source / ".ty1208z-overlay.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (source / ".ty1208z-ethernet-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    (source / ".ty1208z-toolchain.json").write_text(json.dumps(identity, indent=2) + "\n")
    config = (project / "openwrt/config/ram.config").read_text()
    config += (project / "openwrt/ethernet/config").read_text()
    config += (
        "CONFIG_EXTERNAL_TOOLCHAIN=y\n"
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
    prepare_ethernet(Path(__file__).resolve().parents[1], args.taskbase.resolve())


if __name__ == "__main__":
    main()
