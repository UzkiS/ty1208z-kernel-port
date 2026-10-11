#!/usr/bin/env python3
"""Merge explicit Kconfig values; retain other values from allnoconfig."""
import re
import sys
from pathlib import Path

config, fragment = map(Path, sys.argv[1:])
def symbol(line):
    match = re.match(r"(?:# )?(CONFIG_\w+)(?:=| is not set)", line)
    return match[1] if match else None

values = {symbol(line): line for line in fragment.read_text().splitlines() if symbol(line)}
lines = [line for line in config.read_text().splitlines() if symbol(line) not in values]
config.write_text("\n".join(lines + list(values.values())) + "\n")
