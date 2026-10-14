#!/usr/bin/env python3
"""Exercise actual netifd handler discovery against mixed output ending in EOF."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from netifd_wireless_eof import AFTER, BEFORE, ensure


def fixture(source, directory):
    """Return a ucode fixture importing the real patched handler_load function."""
    start = source.index("export function handler_load(")
    end = source.index("export function handler_attributes(", start)
    function = source[start:end].replace("export function", "function", 1)
    return ('import { glob, basename, mkstemp, realpath, chdir } from "fs";\n' + function +
            f'let count = 0; handler_load({directory!r}, function(script, data) {{\n'
            'if (script != "mixed.sh" || data.driver != "rda") die("bad handler"); count++;\n'
            '}); if (count != 2) die("handler count"); print("NETIFD_HANDLER_EOF_PASS\\n");\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ucode", default="ucode")
    args = parser.parse_args()
    assert ensure(BEFORE) == AFTER
    assert ensure(AFTER) == AFTER
    for changed in ("", BEFORE + BEFORE):
        try:
            ensure(changed)
        except ValueError:
            continue
        raise AssertionError("Changed source anchor accepted")
    with tempfile.TemporaryDirectory(prefix="netifd-eof-") as temporary:
        directory = Path(temporary)
        handler = directory / "mixed.sh"
        handler.write_text("#!/bin/sh\nprintf '%s\\n' '' 'invalid' '[]' '{\"driver\":\"rda\"}' '{\"driver\":\"rda\"}'\n")
        handler.chmod(0o755)
        test = directory / "fixture.uc"
        test.write_text(fixture(args.source.read_text(), str(directory)))
        subprocess.run([args.ucode, str(test)], check=True, timeout=5)


if __name__ == "__main__":
    main()
