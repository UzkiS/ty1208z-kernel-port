#!/usr/bin/env python3
"""Prepare existing native userspace for RAM network delivery; never access a board."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile


def record(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def native_archive(directory, filename):
    manifest = json.loads((directory / "manifest.json").read_bytes())
    data = (directory / filename).read_bytes()
    if record(data) != manifest["files"][filename]:
        raise ValueError("Native archive differs from its delivery manifest")
    data = gzip.decompress(data)
    entries = {}
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        if header[:6] != b"070701":
            raise ValueError("Expected the delivered newc archive")
        values = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        _, mode, _, _, links, _, size, _, _, _, _, namesize, _ = values
        offset += 110
        namebytes = data[offset:offset + namesize]
        if not namebytes.endswith(b"\0"):
            raise ValueError("Incomplete cpio name")
        name = namebytes[:-1].decode("utf-8")
        offset = (offset + namesize + 3) & ~3
        payload = data[offset:offset + size]
        if len(payload) != size:
            raise ValueError("Incomplete cpio payload")
        offset = (offset + size + 3) & ~3
        if name == "TRAILER!!!":
            return entries
        while name.startswith("./"):
            name = name[2:]
        if name in ("", "."):
            continue
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or name in entries:
            raise ValueError("Noncanonical or duplicate cpio path")
        entries[name] = (mode, links, payload)
    raise ValueError("Missing cpio trailer")


def prepare(base, combined, output):
    if output.exists():
        raise ValueError("Userspace delivery already exists; inspect rather than overwrite")
    original = native_archive(base, "rootfs.cpio.gz")
    complete = native_archive(combined, "rootfs.native.QEMU-ONLY.cpio.gz")
    components = ("bin/busybox", "lib/libc.so", "lib/libgcc_s.so.1",
                  "usr/bin/xray", "usr/bin/sing-box", "usr/bin/unzip")
    compared = {}
    for name in components:
        if original[name] != complete[name]:
            raise ValueError("Changed application/runtime component: " + name)
        compared[name] = record(complete[name][2])
    passwall = {name for name in original if name.startswith("usr/lib/lua/luci/passwall/")}
    if not passwall or passwall != {name for name in complete if name.startswith("usr/lib/lua/luci/passwall/")}:
        raise ValueError("Passwall source tree differs")
    for name in sorted(passwall):
        if original[name] != complete[name]:
            raise ValueError("Changed installed Passwall source: " + name)
        if stat.S_ISREG(complete[name][0]):
            compared[name] = record(complete[name][2])
    selected = {}
    for name, entry in complete.items():
        if name.startswith(("lib/modules/", "lib/apk/")):
            continue
        permitted = name.startswith(("usr/", "lib/", "sbin/", "bin/", "etc/init.d/", "etc/docker/", "etc/sysctl.d/")) or name == "etc/config/dockerd"
        if permitted and (name not in original or name == "usr/bin/sing-box"):
            mode, links, payload = entry
            if stat.S_ISREG(mode) and links != 1:
                raise ValueError("Supplement needs explicit hardlink handling: " + name)
            if stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                selected[name] = entry
    required = ("usr/bin/docker", "usr/bin/dockerd", "usr/bin/containerd",
                "usr/bin/containerd-shim-runc-v2", "usr/sbin/runc", "usr/bin/tini",
                "usr/bin/sing-box", "etc/init.d/dockerd", "etc/config/dockerd")
    if not set(required) <= selected.keys():
        raise ValueError("Incomplete Docker/sing-box supplement: " + repr(set(required) - selected.keys()))
    buffer = io.BytesIO()
    delivered = {}
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, (mode, _, payload) in sorted(selected.items()):
            member = tarfile.TarInfo(name)
            member.mode, member.mtime = stat.S_IMODE(mode), 1791676800
            if stat.S_ISLNK(mode):
                member.type, member.linkname = tarfile.SYMTYPE, payload.decode("utf-8")
                archive.addfile(member)
                delivered[name] = {"symlink": member.linkname}
            else:
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
                delivered[name] = record(payload)
    packed = gzip.compress(buffer.getvalue(), compresslevel=6, mtime=0)
    output.mkdir(parents=True)
    filename = "userspace-supplement.RAM-ONLY.tar.gz"
    (output / filename).write_bytes(packed)
    receipt = {"schema": 1, "status": "prepared native userspace; not installed or board-tested",
               "kernel_modules": "excluded; use modules from the exact integrated board kernel",
               "scope": "RAM network delivery after the matching integrated kernel boots",
               "base_manifest_sha256": hashlib.sha256((base / "manifest.json").read_bytes()).hexdigest(),
               "combined_manifest_sha256": hashlib.sha256((combined / "manifest.json").read_bytes()).hexdigest(),
               "unchanged_application_files": compared, "supplement_files": delivered,
               "files": {filename: record(packed)}, "hardware_actions": False}
    (output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"prepared": True, "unchanged_application_files": len(compared),
                      "supplement_files": len(delivered), "compressed_bytes": len(packed),
                      "kernel_modules": "excluded", "hardware_actions": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.base, args.combined, args.output)
