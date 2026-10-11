#!/usr/bin/env python3
"""Generate the ARM time64 stat fix against the pinned BusyBox archive."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import tarfile

project = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--archive", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
lock = json.loads((project / "config/sources.lock.json").read_text())
with args.archive.open("rb") as source:
    assert hashlib.file_digest(source, "sha256").hexdigest() == lock["busybox"]["sha256"]
path = "coreutils/stat.c"
with tarfile.open(args.archive) as archive:
    before = archive.extractfile(f'busybox-{lock["busybox"]["version"]}/{path}').read().decode()
after = before
for member in ("st_atime", "st_mtime", "st_ctime"):
    after = after.replace(f"(long) statbuf->{member}", f"(long long) statbuf->{member}")
    after = after.replace(f"(unsigned long) statbuf.{member}", f"(long long) statbuf.{member}")
after = after.replace('TYPE_SIGNED(time_t) ? "ld" : "lu"', 'TYPE_SIGNED(time_t) ? "lld" : "llu"')
after = after.replace(
    '\t\t/* note: (unsigned long) would be wrong:\n'
    '\t\t * imagine (unsigned long64)int32 */\n',
    '\t\t/* time_t may be 64-bit even when long is only 32-bit. */\n')
after = after.replace(
    'printf("%s %llu %llu %lx %lu %lu %llx %llu %lu %lx %lx %lu %lu %lu %lu"',
    'printf("%s %llu %llu %lx %lu %lu %llx %llu %lu %lx %lx %lld %lld %lld %lu"')
assert before != after and after.count('TYPE_SIGNED(time_t) ? "lld" : "llu"') == 3
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                 f"a/{path}", f"b/{path}")), encoding="utf-8", newline="\n")
print(f"Generated {args.output}: stat time64 output without narrowing to long")
