#!/usr/bin/env python3
"""Stream the exact native RO eMMC user area to a new host file; never write the card."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from native_emmc_profile import COMPATIBLE, native_emmc_configuration

SECTORS = 15269888
BYTES = SECTORS * 512
LAYOUT = ((0, 2048), (2048, 2048), (4096, 8192), (12288, 8192), (20480, 8192),
          (28672, 40960), (69632, 131072), (200704, 1048576), (1249280, 14020608))


def guard(fdt_sha256):
    if not re.fullmatch(r"[0-9a-f]{64}", fdt_sha256):
        raise ValueError("Expected an exact FDT SHA-256")
    identity = hashlib.sha256((COMPATIBLE + "\0hi3798mv100-series\0").encode()).hexdigest()
    layout = "\n".join(f"{start} {size}" for start, size in LAYOUT)
    return f'''set -eu
preflight() {{
    test "$(uname -r)" = 6.12.112
    value=$(sha256sum /sys/firmware/devicetree/base/compatible)
    test "${{value%% *}}" = {identity}
    value=$(sha256sum /sys/firmware/fdt)
    test "${{value%% *}}" = {fdt_sha256}
    test "$(cat /sys/class/block/mmcblk0/device/name)" = 008G30
    test "$(cat /sys/class/block/mmcblk0/size)" = {SECTORS}
    test -z "$(grep 'mmcblk0' /proc/mounts)"
    test -z "$(grep -E '^[^ ]+ [^ ]+ 179:' /proc/self/mountinfo)"
    test -z "$(grep 'mmcblk0' /proc/swaps)"
    count=0
    for block in /sys/class/block/*; do
        case "${{block##*/}}" in mmcblk0|mmcblk0p[1-9]) ;; *) return 1 ;; esac
        test "$(cat "$block/ro")" = 1
        count=$(awk -v count="$count" 'BEGIN {{ print count + 1 }}')
    done
    test "$count" = 10
    index=0
    while read -r start size; do
        index=$(awk -v part="$index" 'BEGIN {{ print part + 1 }}')
        test "$(cat "/sys/class/block/mmcblk0p$index/start")" = "$start"
        test "$(cat "/sys/class/block/mmcblk0p$index/size")" = "$size"
    done <<'LAYOUT'
{layout}
LAYOUT
    test "$index" = 9
    test -b /dev/mmcblk0
}}
'''


def stream(process, output, expected_bytes, progress=None):
    """Fail closed on errors/short/extra output; retain an unaccepted partial file."""
    digest = hashlib.sha256()
    received = 0
    last = time.monotonic()
    try:
        with output.open("xb") as destination:
            while chunk := process.stdout.read(1024 * 1024):
                received += len(chunk)
                if received > expected_bytes:
                    raise ValueError("Backup stream exceeds the measured user-area capacity")
                destination.write(chunk)
                digest.update(chunk)
                if progress and time.monotonic() - last >= 20:
                    progress(received)
                    last = time.monotonic()
            destination.flush()
            os.fsync(destination.fileno())
        code = process.wait(timeout=30)
        if code != 0 or received != expected_bytes:
            raise ValueError(f"Backup unaccepted: transport exit={code}, bytes={received}/{expected_bytes}")
        with output.open("rb") as saved:
            if hashlib.file_digest(saved, "sha256").hexdigest() != digest.hexdigest():
                raise ValueError("Saved host backup differs from the received stream")
        return {"bytes": received, "sha256": digest.hexdigest()}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


def backup(settings, artifacts, output):
    manifest = json.loads((artifacts / "manifest.json").read_text())
    if manifest.get("application_variant") != "ethernet-emmcro":
        raise ValueError("Backup requires the independent native read-only eMMC image")
    native_emmc_configuration((artifacts / "linux.config").read_text())
    for name, expected in manifest["files"].items():
        path = artifacts / name
        if not path.resolve().is_relative_to(artifacts.resolve()):
            raise ValueError("Artifact path escapes its manifest directory")
        with path.open("rb") as source:
            actual = {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(source, "sha256").hexdigest()}
        if actual != expected:
            raise ValueError("Changed backup source artifact: " + name)
    script = guard(manifest["files"]["ty1208z-diagnostic.dtb"]["sha256"])
    output = output.resolve()
    partial = output.with_name(output.name + ".partial")
    receipt = output.with_name(output.name + ".json")
    if any(path.exists() for path in (output, partial, receipt)):
        raise ValueError("Backup destination/partial/receipt already exists; choose a new file")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < BYTES + 64 * 1024 * 1024:
        raise ValueError("Host lacks space for the complete eMMC user area")
    ssh = ["ssh", "-i", settings["private_key"], "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
           "-o", "UserKnownHostsFile=" + settings["known_hosts"], "-o", "ConnectTimeout=8",
           "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3"]
    if settings.get("source"):
        ssh += ["-b", settings["source"]]
    host = settings["host"]
    if not re.fullmatch(r"[0-9A-Za-z.:_-]+", host) or host.startswith("-"):
        raise ValueError("Invalid backup SSH host")
    ssh += ["root@" + host, "sh -s"]
    preflight = subprocess.run(ssh, input=(script + "preflight\necho EMMC_RO_BACKUP_PREFLIGHT_PASS\n").encode(),
                               capture_output=True, timeout=30)
    if preflight.returncode != 0 or preflight.stdout != b"EMMC_RO_BACKUP_PREFLIGHT_PASS\n":
        raise ValueError("Exact native identity/readonly/unmounted/layout preflight failed")
    start = datetime.now(timezone.utc).isoformat()
    # Repeat the exact guards on the stream connection. stdout contains only
    # sector data; stderr is stored on the host, never on the box/card.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(ssh, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
        process.stdin.write((script + f"preflight\nexec dd if=/dev/mmcblk0 bs=4096 count={BYTES // 4096}\n").encode())
        process.stdin.close()
        file_record = stream(process, partial, BYTES,
                             lambda count: print(f"EMMC_RO_BACKUP_PROGRESS bytes={count}/{BYTES}", flush=True))
    # The accepted image appears only after exact length, SSH exit and an
    # independent readback hash pass. The complete backup stays private.
    os.link(partial, output)
    partial.unlink()
    record = {"schema": 1, "status": "complete-host-backup-user-area-only", "file": output.name,
              "started_utc": start, "ended_utc": datetime.now(timezone.utc).isoformat(),
              "user_area": file_record, "boot0_boot1_rpmb": "excluded", "card_writes": False,
              "artifact_manifest_sha256": hashlib.sha256((artifacts / "manifest.json").read_bytes()).hexdigest()}
    with receipt.open("x", encoding="utf-8", newline="\n") as saved:
        json.dump(record, saved, indent=2)
        saved.write("\n")
    print("EMMC_RO_HOST_BACKUP_PASS " + json.dumps(file_record), flush=True)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-config", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    backup(json.loads(args.ssh_config.read_text()), args.artifacts.resolve(), args.output)
