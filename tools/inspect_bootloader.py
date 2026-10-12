#!/usr/bin/env python3
"""Extract the known CA bootloader's LZMA payload locally, without executing it."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re

SOURCE_SHA256 = "f891870ec98b4df48de879afc1e1973cf14cc9057eb18a5a41d974fab3e935bc"
LZMA_OFFSET = 31128
PAYLOAD_SHA256 = "a1181bf31bef0ac8a0da40b6a1ecdaf142304e041255f559735361c1e0567b83"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Local evidence directory")
    args = parser.parse_args()
    data = args.input.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error("Input is not the measured known-successful CA fastboot")
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=64 * 1024 * 1024)
    payload = decoder.decompress(data[LZMA_OFFSET:], max_length=8 * 1024 * 1024)
    if not decoder.eof or hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA256:
        parser.error("Unexpected decompression result")
    strings = [item.decode("ascii") for item in re.findall(rb"[ -~]{4,}", payload)]
    relevant = [item for item in strings if any(word in item.lower() for word in (
        "help", "printenv", "autoboot", "bootm", "bootcmd", "loadb", "tftp", "fastboot#",
    ))]
    report = {
        "source_sha256": SOURCE_SHA256, "lzma_offset": LZMA_OFFSET,
        "payload_bytes": len(payload), "payload_sha256": PAYLOAD_SHA256,
        "status": "offline-string-evidence; not runtime command validation",
        "relevant_strings": relevant,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, blob in (
        ("ca-bootloader-payload.bin", payload),
        ("ca-bootloader-strings.txt", ("\n".join(strings) + "\n").encode()),
        ("ca-bootloader-audit.json", (json.dumps(report, indent=2) + "\n").encode()),
    ):
        destination = args.output / filename
        with destination.open("xb") as stream:
            stream.write(blob)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
