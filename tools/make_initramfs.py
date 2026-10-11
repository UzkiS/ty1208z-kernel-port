#!/usr/bin/env python3
"""Deterministic newc archive with console node, without host mknod/root."""
import os
from pathlib import Path
import stat
import sys

root, output = map(Path, sys.argv[1:])
archive = bytearray()
inode = 0

def add(name, mode, payload=b"", rmajor=0, rminor=0):
    global inode
    inode += 1
    encoded = name.encode() + b"\0"
    fields = (inode, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1,
              1791676800, len(payload), 0, 0, rmajor, rminor, len(encoded), 0)
    archive.extend(b"070701" + "".join(f"{value:08x}" for value in fields).encode())
    archive.extend(encoded)
    archive.extend(b"\0" * (-len(archive) % 4))
    archive.extend(payload)
    archive.extend(b"\0" * (-len(archive) % 4))

add(".", stat.S_IFDIR | 0o755)
for path in sorted(root.rglob("*")):
    name = path.relative_to(root).as_posix()
    if path.is_symlink():
        add(name, stat.S_IFLNK | 0o777, os.readlink(path).encode())
    elif path.is_dir():
        add(name, stat.S_IFDIR | (0o1777 if name == "tmp" else 0o755))
    elif path.is_file():
        add(name, stat.S_IFREG | (path.stat().st_mode & 0o777), path.read_bytes())
add("dev/console", stat.S_IFCHR | 0o600, rmajor=5, rminor=1)
add("dev/null", stat.S_IFCHR | 0o666, rmajor=1, rminor=3)
add("TRAILER!!!", 0)
archive.extend(b"\0" * (-len(archive) % 512))
output.write_bytes(archive)
print(f"Initramfs: {len(archive)} bytes, reproducible ownership and timestamps")
