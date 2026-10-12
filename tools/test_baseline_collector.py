#!/usr/bin/env python3
"""Run the read-only collector locally, including Windows stdin line endings."""
from pathlib import Path
import subprocess


def main():
    collector = (Path(__file__).resolve().parent / "collect-baseline.sh").read_bytes()
    for name, suffix in (("LF", b"\n"), ("Windows PowerShell CRLF", b"\r\n")):
        result = subprocess.run(
            ["sh", "-s"], input=collector + suffix,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{name}: exit {result.returncode}: {result.stderr.decode(errors='replace')}")
        lines = result.stdout.splitlines()
        if not lines or lines[0] != b"TY1208Z_READONLY_BASELINE_BEGIN" or lines[-1] != b"TY1208Z_READONLY_BASELINE_END":
            raise RuntimeError(f"{name}: incomplete report")
        if result.stderr:
            raise RuntimeError(f"{name}: unexpected stderr: {result.stderr.decode(errors='replace')}")
        print(f"Read-only collector passed with {name}; complete report, exit 0")


if __name__ == "__main__":
    main()
