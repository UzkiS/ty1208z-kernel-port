#!/usr/bin/env python3
"""Bound pinned netifd handler discovery by EOF, not only by file errors."""
from pathlib import Path

RELATIVE = Path("package/network/config/netifd/files/lib/netifd/utils.uc")
BEFORE = '''\t\twhile (!f.error()) {
\t\t\tlet data = trim(f.read("line"));'''
AFTER = '''\t\twhile (true) {
\t\t\tlet line = f.read("line");
\t\t\tif (line == null)
\t\t\t\tbreak;
\t\t\tlet data = trim(line);'''


def ensure(text):
    if text.count(AFTER) == 1 and BEFORE not in text:
        return text
    if text.count(BEFORE) != 1 or AFTER in text:
        raise ValueError("Pinned netifd handler EOF anchor changed")
    return text.replace(BEFORE, AFTER)


def apply(source):
    path = source / RELATIVE
    original = path.read_text()
    patched = ensure(original)
    if patched != original:
        path.write_text(patched)
    return path
