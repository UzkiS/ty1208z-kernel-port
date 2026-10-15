#!/usr/bin/env python3
"""Install native applications offline with exact-board module APKs into a RAM delivery."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile

from prepare_native_userspace import native_archive, record


REQUIRED = ("docker", "dockerd", "containerd", "runc", "tini", "luci-app-dockerman",
            "luci-i18n-dockerman-zh-cn", "docker-compose", "ttyd", "luci-app-ttyd",
            "luci-i18n-ttyd-zh-cn", "ucode-mod-socket",
            "iw-full", "wpad-mbedtls", "hostapd-common", "wireless-regdb", "wifi-scripts",
            "ucode-mod-nl80211", "ucode-mod-rtnl", "block-mount", "lsblk",
            "luci-app-diskman", "luci-i18n-diskman-zh-cn", "parted", "e2fsprogs",
            "dosfstools", "exfat-mkfs", "exfat-fsck", "blkid", "smartmontools")
ARCH = "arm_cortex-a7_neon-vfpv4"
EPOCH = "1791676800"
PROJECT = Path(__file__).resolve().parents[1]
BOARD_FILES = {
    "etc/uci-defaults/96-ty1208z-ethernet-mac": "openwrt/system/ethernet-mac",
    "etc/uci-defaults/98-ty1208z-docker-network": "openwrt/system/docker-network",
    "lib/netifd/wireless/rda.sh": "openwrt/system/wireless/rda.sh",
    "etc/uci-defaults/97-ty1208z-wireless": "openwrt/system/wireless/defaults",
    "usr/libexec/ty1208z-rda-path": "openwrt/system/wireless/rda-path",
    "etc/hotplug.d/ieee80211/05-ty1208z-rda-path": "openwrt/system/wireless/hotplug",
}
PERSISTENT_BOARD_FILES = {
    "lib/preinit/79-ty1208z-disk-root": "openwrt/system/persistent/79-ty1208z-disk-root",
    "etc/ty1208z-disk-root": "openwrt/system/persistent/root-marker",
}


def board_files(kernel_build):
    files = dict(BOARD_FILES)
    if "CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE=y\n" in (kernel_build / ".config").read_text():
        files.update(PERSISTENT_BOARD_FILES)
    return files


def run(command, **kwargs):
    return subprocess.check_output([str(p) for p in command], **kwargs)


def public_runtime_metadata(root):
    """Normalize informational origins, retaining all APK payload checksums."""
    database = root / 'lib/apk/db/installed'
    lines = database.read_text().splitlines(True)
    for index, line in enumerate(lines):
        if line.startswith('o:/'):
            if '/feeds/' not in line:
                raise ValueError('Review unexpected absolute APK origin')
            lines[index] = 'o:feeds/' + line.split('/feeds/', 1)[1]
    database.write_text(''.join(lines))
    # Host APK invocation logs and unowned cross-GDB auto-load files are not
    # runtime content. The latter refer only to the build host's Python tree.
    (root / 'tmp/log/apk.log').unlink(missing_ok=True)
    for path in (root / 'lib').glob('libstdc++.so.*-gdb.py'):
        path.unlink()


def metadata(apk, package):
    return json.loads(run([apk, "adbdump", "--format", "json", package]))


def unpack_entries(entries, destination):
    for name, (mode, links, payload) in entries.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if stat.S_ISDIR(mode):
            path.mkdir(exist_ok=True)
        elif stat.S_ISLNK(mode):
            path.symlink_to(payload.decode())
        elif stat.S_ISREG(mode):
            if links != 1:
                raise ValueError("Unsupported native hardlink: " + name)
            path.write_bytes(payload)
            path.chmod(stat.S_IMODE(mode))


def installed_names(entries):
    return {line[2:] for line in entries["lib/apk/db/installed"][2].decode().splitlines()
            if line.startswith("P:")}


def check_accounts(name, before, after):
    """Keep native identities/passwords; allow package-added group memberships."""
    old_rows = [line.split(b":") for line in before.splitlines()]
    new_rows = [line.split(b":") for line in after.splitlines()]
    old = {row[0]: row for row in old_rows}
    new = {row[0]: row for row in new_rows}
    if len(old) != len(old_rows) or len(new) != len(new_rows):
        raise ValueError("Duplicate account identity: " + name)
    for identity, row in old.items():
        actual = new.get(identity)
        if name == "etc/group" and actual and len(row) == len(actual) == 4:
            valid = row[:3] == actual[:3] and set(filter(None, row[3].split(b","))) <= set(actual[3].split(b","))
        else:
            valid = row == actual
        if not valid:
            raise ValueError("Existing native account changed: " + name)


def candidates_from_sources(baseline_source, source):
    candidates = {}
    for tree in (baseline_source, source):
        for package in sorted((tree / "bin").rglob("*.apk")):
            match = re.fullmatch(r"(.+?)-([0-9].*)\.apk", package.name)
            if not match:
                raise ValueError("Unexpected APK filename: " + package.name)
            candidates[match[1]] = package
    return candidates


def input_provenance(base, source, baseline_source, board_root, kernel_build):
    """Bind cached transactions to actual native APK and board-module payloads."""
    def digest(path):
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    modules = board_root / "lib/modules/6.12.112"
    provenance = {
        "preparer_sha256": digest(Path(__file__)),
        "docker_startup_preparer_sha256": digest(PROJECT / "tools/native_docker_startup.py"),
        "board_files": {name: digest(PROJECT / path) for name, path in board_files(kernel_build).items()},
        "base_rootfs_sha256": digest(base / "rootfs.cpio.gz"),
        "native_config_sha256": digest(source / ".config"),
        "baseline_config_sha256": digest(baseline_source / ".config"),
        "kernel_config_sha256": digest(kernel_build / ".config"),
        "kernel_image_sha256": digest(kernel_build / "arch/arm/boot/zImage"),
        "native_apks": {name: {"filename": p.name, "sha256": digest(p)}
                        for name, p in sorted(candidates_from_sources(baseline_source, source).items())},
        "board_modules": {p.name: digest(p) for p in sorted(modules.glob("*")) if p.is_file()},
    }
    if "CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE=y\n" in (kernel_build / ".config").read_text():
        from native_upgrade import source_identity
        provenance["web_upgrade_sources"] = source_identity()
    return provenance


def make_kernel_packages(apk, candidates, board_root, kernel_build, repository, work):
    modules = board_root / "lib/modules/6.12.112"
    builtins = {Path(line).name for line in (modules / "modules.builtin").read_text().splitlines()}
    identity = hashlib.sha256((kernel_build / ".config").read_bytes() +
                              (kernel_build / "arch/arm/boot/zImage").read_bytes()).hexdigest()
    version = "6.12.112~" + identity[:32] + "-r1"
    packages, omitted = {}, {}
    kernel_root = work / "kernel"
    kernel_root.mkdir()
    for name, path in board_files(kernel_build).items():
        destination = kernel_root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / path, destination)
        destination.chmod(0o644 if name == "etc/ty1208z-disk-root" else 0o755)
    target = kernel_root / "lib/modules/6.12.112"
    target.mkdir(parents=True)
    for name in ("modules.builtin", "modules.builtin.modinfo", "modules.dep", "modules.alias",
                 "modules.order", "rdawfmac.ko"):
        shutil.copyfile(modules / name, target / name)
    kernel_output = repository / ("kernel-" + version + ".apk")
    packages["kernel"] = kernel_output
    owned = {"rdawfmac.ko"}
    for name, package in sorted(candidates.items()):
        if not name.startswith("kmod-"):
            continue
        info = metadata(apk, package)["info"]
        extracted = work / name
        extracted.mkdir()
        run([apk, "extract", "--allow-untrusted", "--no-chown", "--destination", extracted, package])
        missing = []
        for module in extracted.rglob("*.ko"):
            actual = modules / module.name
            if actual.is_file():
                shutil.copyfile(actual, module)
            elif module.name in builtins:
                module.unlink()
            else:
                missing.append(module.name)
        if missing:
            omitted[name] = missing
            continue
        owned.update(p.name for p in extracted.rglob("*.ko"))
        # Own only files that are present in this board build; builtins belong to kernel.
        listing = extracted / ("lib/apk/packages/" + name + ".list")
        if listing.exists():
            listing.write_text("".join("/" + p.relative_to(extracted).as_posix() + "\n"
                                     for p in sorted(extracted.rglob("*"))
                                     if p.is_file() and p != listing))
        depends = ["kernel=" + version if d.startswith("kernel=") else d
                   for d in info.get("depends", [])]
        output = repository / (name + "-6.12.112-r2.apk")
        run([apk, "mkpkg", "--files", extracted, "--output", output,
             "--info", "name:" + name, "--info", "version:6.12.112-r2",
             "--info", "arch:" + ARCH, "--info", "license:" + info["license"],
             "--info", "description:Exact TY1208Z system build: " + info["description"],
             "--info", "depends:" + " ".join(depends),
             "--info", "provides:" + " ".join(info.get("provides", []))])
        packages[name] = output
    # Modules with no native feed package still need a real APK owner (e.g.
    # this kernel's mptcp_diag). Keep them in the exact-board kernel package.
    for module in sorted(modules.glob("*.ko")):
        if module.name not in owned:
            shutil.copyfile(module, target / module.name)
    run([apk, "mkpkg", "--files", kernel_root, "--output", kernel_output,
         "--info", "name:kernel", "--info", "version:" + version,
         "--info", "arch:" + ARCH, "--info", "license:GPL-2.0-only",
         "--info", "description:Exact TY1208Z RAM system kernel metadata and supplemental modules",
         "--info", "depends:libc", "--info", "provides:kernel-any"])
    return packages, omitted, identity


def prepare(base, source, baseline_source, board_root, kernel_build, output):
    base, source, baseline_source, board_root, kernel_build, output = (
        path.resolve() for path in (base, source, baseline_source, board_root, kernel_build, output))
    if output.exists():
        raise ValueError("Inspect existing package delivery before replacing it")
    original = native_archive(base, "rootfs.cpio.gz")
    output.mkdir(parents=True)
    work = output / "work"
    work.mkdir()
    root = output / "root"
    root.mkdir()
    unpack_entries(original, root)
    apk = source / "staging_dir/host/bin/apk"
    candidates = candidates_from_sources(baseline_source, source)
    repository = output / "packages"
    repository.mkdir()
    environment = dict(os.environ, SOURCE_DATE_EPOCH=EPOCH, TZ="UTC", LC_ALL="C")
    previous = os.environ.get("SOURCE_DATE_EPOCH")
    os.environ["SOURCE_DATE_EPOCH"] = EPOCH
    try:
        from native_docker_startup import make_package as make_docker_package
        candidates["dockerd"] = make_docker_package(apk, candidates["dockerd"], work / "dockerd-startup")
        kernel_packages, omitted, kernel_identity = make_kernel_packages(
            apk, candidates, board_root, kernel_build, repository, work)
        if "CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE=y\n" in (kernel_build / ".config").read_text():
            from native_upgrade import make_package
            compilers = list((baseline_source / "staging_dir").glob(
                "toolchain-arm*/bin/arm-openwrt-linux-muslgnueabi-gcc"))
            if len(compilers) != 1:
                raise ValueError("Exact native upgrade helper compiler missing")
            version = "6.12.112~" + kernel_identity[:32] + "-r1"
            package = make_package(compilers[0], apk, version, work / "upgrade-package")
            destination = repository / package.name
            shutil.copyfile(package, destination)
            kernel_packages["ty1208z-upgrade"] = destination
    finally:
        if previous is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = previous
    names = installed_names(original)
    if names & omitted.keys():
        raise ValueError("Board kernel lacks previously installed module packages: " + repr(names & omitted.keys()))
    for name, package in candidates.items():
        if name == "kernel" or name.startswith("kmod-"):
            continue
        (repository / package.name).symlink_to(package.resolve())
    all_packages = sorted(repository.glob("*.apk"))
    run([apk, "mkndx", "--allow-untrusted", "--output", repository / "packages.adb", *all_packages])
    # Keep the native filesystem and accounts, then let apk recreate the database
    # from real package payloads. Scripts execute offline in the next host-shell stage.
    shutil.rmtree(root / "lib/apk")
    for path in (root / "lib/modules", root / "etc/modules.d", root / "etc/modules-boot.d"):
        if path.exists():
            shutil.rmtree(path)
    (root / "etc/apk/world").unlink()
    selection = sorted(names | set(REQUIRED) | {"kmod-nft-nat"} |
                       ({"ty1208z-upgrade"} if "ty1208z-upgrade" in kernel_packages else set()))
    log = output / "apk-install.log"
    with log.open("wb") as handle:
        subprocess.run([str(apk), "add", "--root", str(root), "--initdb", "--usermode",
                        "--arch", ARCH, "--allow-untrusted", "--no-network", "--no-scripts",
                        "--no-commit-hooks", "--repositories-file", "/dev/null",
                        "--repository", str(repository / "packages.adb"), *selection],
                       check=True, stdout=handle, stderr=subprocess.STDOUT, env=environment)
    (root / "tmp/lock").mkdir(parents=True, exist_ok=True)
    # Execute package post-install scripts using OpenWrt's offline-root convention.
    scripts = root / "lib/apk/db/scripts.tar"
    with tarfile.open(str(scripts) + ".gz", "r:gz") as archive:
        for member in archive:
            if not member.name.endswith(".post-install"):
                continue
            payload = archive.extractfile(member).read()
            script = work / Path(member.name).name
            script.write_bytes(payload)
            with log.open("ab") as handle:
                subprocess.run(["bash", str(script)], check=True, stdout=handle, stderr=subprocess.STDOUT,
                               env=dict(environment, IPKG_INSTROOT=str(root), IPKG_NO_SCRIPT="0"))
    # Preserve the measured board network, native RAM entry and Chinese/empty-password defaults.
    for name in ("init", "etc/config/network"):
        (root / name).write_bytes(original[name][2])
        (root / name).chmod(stat.S_IMODE(original[name][0]))
    for name in ("bin/busybox", "lib/libc.so", "lib/libgcc_s.so.1", "usr/bin/xray",
                 "usr/bin/sing-box", "usr/bin/unzip"):
        if (root / name).read_bytes() != original[name][2]:
            raise ValueError("Accepted native application/runtime changed: " + name)
    for name, (_, _, data) in original.items():
        if name.startswith("usr/lib/lua/luci/passwall/") and (root / name).is_file():
            if (root / name).read_bytes() != data:
                raise ValueError("Accepted Passwall source changed: " + name)
    installed = run([apk, "query", "--root", root, "--installed", "--format", "json", *REQUIRED])
    records = json.loads(installed)
    if {r["name"] for r in records} != set(REQUIRED):
        raise ValueError("Incomplete installed application/wireless package set")
    expected_modules = {p.name: p.read_bytes() for p in (board_root / "lib/modules/6.12.112").glob("*.ko")}
    actual_modules = {p.name: p.read_bytes() for p in (root / "lib/modules/6.12.112").glob("*.ko")}
    if actual_modules != expected_modules:
        raise ValueError("APK transaction does not own every exact-board module")
    public_runtime_metadata(root)
    subprocess.run([sys.executable, PROJECT / "tools/test_rda_radio_path.py", "--root", root], check=True)
    subprocess.run([sys.executable, PROJECT / "tools/test_ethernet_mac.py", "--root", root], check=True)
    subprocess.run([sys.executable, PROJECT / "tools/test_wireless_defaults.py", "--root", root], check=True)
    # Archive every actual difference plus all metadata, so software management
    # describes the delivered files. The board module APKs own their exact payloads.
    delivered = {}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() and not path.is_symlink():
                continue
            name = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            data = str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
            entry = (mode, 1, data)
            if (name in original and original[name] == entry and name != "usr/bin/xray" and
                    not name.startswith(("lib/apk/", "lib/modules/"))):
                continue
            if name in ("etc/passwd", "etc/group", "etc/shadow"):
                check_accounts(name, original[name][2], data)
            member = tarfile.TarInfo(name)
            member.mode, member.mtime = stat.S_IMODE(mode), int(EPOCH)
            if path.is_symlink():
                member.type, member.linkname = tarfile.SYMTYPE, data.decode()
                archive.addfile(member)
                delivered[name] = {"symlink": member.linkname}
            else:
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
                delivered[name] = record(data)
    packed = gzip.compress(buffer.getvalue(), compresslevel=6, mtime=0)
    filename = "userspace-packages.RAM-ONLY.tar.gz"
    (output / filename).write_bytes(packed)
    receipt = {"schema": 1, "status": "native package transaction prepared; physical GUI unverified",
               "base_manifest_sha256": hashlib.sha256((base / "manifest.json").read_bytes()).hexdigest(),
               "kernel_identity": kernel_identity, "kernel_packages": sorted(kernel_packages),
               "input_provenance": input_provenance(base, source, baseline_source, board_root, kernel_build),
               "unsupported_unselected_kernel_packages": omitted, "installed_required_packages": records,
               "package_database": "real offline APK transaction with exact-board module packages",
               "supplement_files": delivered, "files": {filename: record(packed)},
               "hardware_actions": False, "persistent_writes": False}
    (output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "packages": len(selection),
                      "supplement_bytes": len(packed), "required_packages": len(records)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "source", "baseline-source", "board-root", "kernel-build", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.base, args.source, args.baseline_source, args.board_root, args.kernel_build, args.output)
