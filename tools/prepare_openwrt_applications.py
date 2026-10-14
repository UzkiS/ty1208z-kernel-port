#!/usr/bin/env python3
"""Prepare isolated native application sources with complete pinned feed archives."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

from prepare_openwrt import extract, prepare, sha256, toolchain_from_native


def pinned_feeds(project, taskbase):
    lock = json.loads((project / "openwrt/applications/sources.lock.json").read_text())
    lines = []
    destinations = {}
    for item in lock["feeds"]:
        archive = taskbase / "downloads" / item["archive"]
        if not archive.exists():
            partial = archive.with_suffix(archive.suffix + ".partial")
            urllib.request.urlretrieve(item["url"], partial)
            if sha256(partial) != item["sha256"]:
                raise ValueError(f"Downloaded feed hash mismatch: {item['name']}")
            partial.replace(archive)
        if sha256(archive) != item["sha256"]:
            raise ValueError(f"Cached feed hash mismatch: {item['name']}")
        destination = taskbase / "applications/feeds" / (item["name"] + "-" + item["commit"])
        marker = destination / ".ty1208z-feed.json"
        if destination.exists():
            if not marker.exists() or json.loads(marker.read_text()) != item:
                raise ValueError(f"Unrecognized feed source: {destination}")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="feed-extract-", dir=destination.parent) as temporary:
                extracted = Path(temporary) / "source"
                extracted.mkdir()
                extract(archive, extracted, item["archive_root"])
                (extracted / marker.name).write_text(json.dumps(item, indent=2) + "\n")
                extracted.rename(destination)
        if any(char.isspace() for char in str(destination)):
            raise ValueError("OpenWrt src-link feed paths must not contain whitespace")
        lines.append(f"src-link {item['name']} {destination}\n")
        destinations[item["name"]] = destination
    for item in lock.get("recipe_patches", []):
        destination = destinations[item["feed"]]
        recipe = destination / item["path"]
        if not recipe.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Recipe patch escapes its pinned feed")
        digest = sha256(recipe)
        if digest == item["original_sha256"]:
            patch = project / "openwrt/applications" / item["patch"]
            subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", str(patch)],
                           cwd=destination, check=True, stdout=subprocess.PIPE)
        if sha256(recipe) != item["patched_sha256"]:
            raise ValueError(f"Recipe patch identity differs: {recipe}")
    for item in lock.get("source_patches", []):
        destination = destinations[item["feed"]]
        recipe = destination / item["recipe"]
        output = destination / item["path"]
        patch = project / "openwrt/applications" / item["patch"]
        if (not recipe.resolve().is_relative_to(destination.resolve()) or
                not output.resolve().is_relative_to(destination.resolve()) or
                not patch.resolve().is_relative_to((project / "openwrt/applications").resolve())):
            raise ValueError("Source patch escapes its pinned application paths")
        if (sha256(recipe) != item["recipe_sha256"] or
                f"PKG_HASH:={item['source_sha256']}\n" not in recipe.read_text() or
                sha256(patch) != item["sha256"]):
            raise ValueError(f"Source patch/recipe identity differs: {item['path']}")
        if output.exists() and sha256(output) != item["sha256"]:
            raise ValueError(f"Existing source patch differs: {item['path']}")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(patch, output)
    return "".join(lines), lock


def application_variant(source):
    marker = source / ".ty1208z-application-variant.json"
    if not marker.exists():
        return "qemu"
    record = json.loads(marker.read_text())
    if record not in tuple({"schema": 1, "variant": variant}
                           for variant in ("qemu", "ethernet", "ethernet-ram768", "ethernet-sdro", "container-qemu")):
        raise ValueError("Unrecognized application source variant")
    return record["variant"]


def merge_kernel_fragment(original, extra):
    # Resolve duplicate symbols before OpenWrt merges its target fragments.
    # Keep the plain application's authoritative fragment unchanged.
    def symbol(line):
        return line.split("=", 1)[0] if line.startswith("CONFIG_") else (
            line.split()[1] if line.startswith("# CONFIG_") else None)
    replacements = {symbol(line) for line in extra.splitlines() if symbol(line)}
    kept = [line for line in original.splitlines() if symbol(line) not in replacements]
    return "\n".join(kept) + "\n" + extra


def prepare_applications(project, taskbase, ethernet=False, container_packages=False, ram768=False, sdro=False,
                         container_applications=False):
    if container_applications and (ethernet or container_packages or ram768 or sdro):
        raise ValueError("Combined container applications require their independent QEMU-only source")
    if sdro and (not ethernet or container_packages or ram768):
        raise ValueError("Native read-only SD requires its independent Ethernet variant")
    if ram768 and (not ethernet or container_packages):
        raise ValueError("Native higher memory requires its independent Ethernet RAM variant")
    if ethernet and container_packages:
        raise ValueError("Container package compilation must remain separate from router RAM builds")
    toolchain, identity = toolchain_from_native(project, taskbase)
    feeds_config, lock = pinned_feeds(project, taskbase)
    appbase = taskbase / ("container-applications" if container_applications else "container-packages" if container_packages else
                          "router-sd" if sdro else "router768" if ram768 else "router" if ethernet else "applications")
    appbase.mkdir(parents=True, exist_ok=True)
    downloads = appbase / "downloads"
    if not downloads.exists():
        downloads.symlink_to(taskbase / "downloads", target_is_directory=True)
    if downloads.resolve() != (taskbase / "downloads").resolve():
        raise ValueError("Application download cache differs from the fixed taskbase")
    with redirect_stdout(io.StringIO()):
        source = prepare(project, appbase)
    manifest = json.loads((source / ".ty1208z-overlay.json").read_text())
    for path in sorted((project / "openwrt/applications/overlay").rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project / "openwrt/applications/overlay")
        output = source / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)
        manifest[str(relative)] = sha256(output)

    if ethernet:
        relative = "target/linux/hi3798mv100/apps/config-6.12"
        path = source / relative
        path.write_text(merge_kernel_fragment(
            path.read_text(), (project / "openwrt/router/kernel.config").read_text()))
        if ram768:
            path.write_text(merge_kernel_fragment(
                path.read_text(), (project / "openwrt/router768/kernel.config").read_text()))
        if sdro:
            path.write_text(merge_kernel_fragment(
                path.read_text(), (project / "openwrt/router-sd/kernel.config").read_text()))
        manifest[relative] = sha256(path)
        # The application candidate is a DHCP client only, with peer DNS for
        # normal name resolution and the installed NTP service.
        relative = "target/linux/hi3798mv100/base-files/etc/config/network"
        shutil.copyfile(project / "openwrt/router/overlay" / relative, source / relative)
        manifest[relative] = sha256(source / relative)

    if container_packages:
        relative = "target/linux/hi3798mv100/apps/config-6.12"
        path = source / relative
        path.write_text(merge_kernel_fragment(
            path.read_text(), (project / "openwrt/containers/kernel.config").read_text()))
        manifest[relative] = sha256(path)
    if container_applications:
        relative = "target/linux/hi3798mv100/apps/config-6.12"
        path = source / relative
        path.write_text(merge_kernel_fragment(
            path.read_text(), (project / "openwrt/containers/applications-kernel.config").read_text()))
        manifest[relative] = sha256(path)

    relative = Path("target/linux/hi3798mv100/Makefile")
    makefile = source / relative
    content = makefile.read_text()
    if content.count("SUBTARGETS:=ram\n") != 1:
        raise ValueError("Native subtarget anchor changed")
    makefile.write_text(content.replace("SUBTARGETS:=ram\n", "SUBTARGETS:=ram apps\n"))
    manifest[str(relative)] = sha256(makefile)
    relative = Path("target/linux/hi3798mv100/image/Makefile")
    makefile = source / relative
    original = makefile.read_text()
    anchor = "include $(INCLUDE_DIR)/image.mk\n"
    if original.count(anchor) != 1:
        raise ValueError("Native image include anchor changed")
    # SUBTARGET is resolved by image.mk -> kernel.mk -> target.mk. Dispatching
    # before that include silently selects the board profile for an apps build.
    makefile.write_text(original.replace(
        anchor, anchor + "\nifeq ($(SUBTARGET),apps)\n"
        "include $(TOPDIR)/target/linux/hi3798mv100/apps/image.mk\n"
        "else\n") + "endif\n")
    manifest[str(relative)] = sha256(makefile)
    (source / "feeds.conf").write_text(feeds_config)
    (source / ".ty1208z-overlay.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (source / ".ty1208z-application-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    (source / ".ty1208z-toolchain.json").write_text(json.dumps(identity, indent=2) + "\n")
    (source / ".ty1208z-application-variant.json").write_text(json.dumps(
        {"schema": 1, "variant": "container-qemu" if container_applications else "ethernet-sdro" if sdro else "ethernet-ram768" if ram768 else "ethernet" if ethernet else "qemu"}, indent=2) + "\n")
    config = (project / "openwrt/config/ram.config").read_text()
    config += (project / ("openwrt/containers/config" if container_packages else
                         "openwrt/applications/config")).read_text()
    if container_applications:
        config = merge_kernel_fragment(config, (project / "openwrt/containers/applications.config").read_text())
    if ethernet:
        config += (project / "openwrt/router/config").read_text()
    if ram768:
        config += (project / "openwrt/router768/config").read_text()
    if sdro:
        config += (project / "openwrt/router-sd/config").read_text()
    config += (
        "CONFIG_EXTERNAL_TOOLCHAIN=y\n"
        f"CONFIG_TOOLCHAIN_ROOT={json.dumps(str(toolchain))}\n"
        'CONFIG_TARGET_NAME="arm-openwrt-linux-muslgnueabi"\n'
        'CONFIG_TOOLCHAIN_PREFIX="arm-openwrt-linux-muslgnueabi-"\n'
        'CONFIG_EXTERNAL_GCC_VERSION="14.3.0"\n'
        "CONFIG_EXTERNAL_TOOLCHAIN_LIBC_USE_MUSL=y\n")
    (source / ".config").write_text(config)
    (source / ".ty1208z-application.config").write_text(config)
    if container_packages:
        (source / ".ty1208z-container-compile-only.json").write_text(json.dumps({
            "schema": 1, "scope": "native Docker packages only; no rootfs/boot/runtime acceptance",
            "config_sha256": sha256(project / "openwrt/containers/config"),
        }, indent=2) + "\n")
    if container_applications:
        (source / ".ty1208z-container-qemu-only.json").write_text(json.dumps({
            "schema": 1, "scope": "combined native applications and Docker for isolated QEMU only; no board image",
            "config_sha256": sha256(project / "openwrt/containers/applications.config"),
        }, indent=2) + "\n")
    print(source)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taskbase", type=Path, required=True)
    parser.add_argument("--ethernet", action="store_true", help="Use separate router build with measured Ethernet support")
    parser.add_argument("--container-packages", action="store_true", help="Separate compile-only Docker packages")
    parser.add_argument("--container-applications", action="store_true", help="Combined native applications/Docker; QEMU only")
    parser.add_argument("--ram768", action="store_true", help="Independent bounded higher-memory router")
    parser.add_argument("--sd-read-only", action="store_true", help="Independent native read-only SD router")
    args = parser.parse_args()
    prepare_applications(Path(__file__).resolve().parents[1], args.taskbase.resolve(),
                         args.ethernet, args.container_packages, args.ram768, args.sd_read_only, args.container_applications)


if __name__ == "__main__":
    main()
