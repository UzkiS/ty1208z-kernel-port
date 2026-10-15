"""Replace an exact earlier board patch without losing OpenWrt generic patches."""
import hashlib
import os
from pathlib import Path
import re
import subprocess


def refresh(kernel, previous, current, *, log):
    previous, current = Path(previous), Path(current)
    if previous.read_bytes() == current.read_bytes():
        return
    paths = set(re.findall(r'^(?:--- a/|\+\+\+ b/)([^\n]+)$',
                           previous.read_text() + current.read_text(), re.MULTILINE))
    unchanged = {}
    for name in paths:
        path = kernel / name
        if not path.resolve().is_relative_to(kernel.resolve()):
            raise ValueError('Board patch path escapes kernel')
        if path.is_file():
            unchanged[name] = (path.read_bytes(), path.stat())
    for patch, reverse in ((previous, True), (current, False)):
        command = ["patch", "--batch", "--fuzz=0", "-p1", "-d", str(kernel)]
        command.append("--reverse" if reverse else "--forward")
        for dry in (True, False):
            with patch.open("rb") as stream:
                subprocess.run(command + (["--dry-run"] if dry else []),
                               stdin=stream, stdout=log, stderr=subprocess.STDOUT,
                               check=True)
    # Preserve incremental builds when an unchanged header appears in both
    # patch versions; only the actual source delta should trigger recompilation.
    for name, (content, stat) in unchanged.items():
        path = kernel / name
        if path.is_file() and path.read_bytes() == content:
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def identity(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
