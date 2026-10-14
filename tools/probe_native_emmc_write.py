#!/usr/bin/env python3
"""Plan, or explicitly execute, one p9 sector write/readback/restore in RAM."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

SECTOR = 15269887
PARTITION_SECTOR = 14020607
CAPACITY = 7818182656


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--control", type=Path, help="Directory containing the compiled fixed-device helper and manifest")
    parser.add_argument("--apply", action="store_true", help="Only after explicit user storage-write authorization")
    args = parser.parse_args()
    manifest = json.loads((args.artifacts / "manifest.json").read_bytes())
    assert manifest.get("persistent_candidate") is True
    plan = {"user_area_sector": SECTOR, "byte_offset": SECTOR * 512, "bytes": 512,
            "target": "last sector of measured eMMC p9", "original_restored_before_success": True,
            "filesystem_must_be_unmounted": True, "persistent_boot_changes": False,
            "requires_specific_user_write_authorization": True}
    if not args.apply:
        print(json.dumps(plan, indent=2))
        return
    assert args.settings and args.backup and args.output and args.control
    control_manifest = json.loads((args.control / "manifest.json").read_bytes())
    assert control_manifest["file"] == "emmc-p9-control.arm"
    control = (args.control / control_manifest["file"]).read_bytes()
    assert len(control) == control_manifest["bytes"]
    assert hashlib.sha256(control).hexdigest() == control_manifest["sha256"]
    assert not args.output.exists(), "Keep each write receipt and preimage independently"
    backup = json.loads(Path(str(args.backup) + ".json").read_bytes())
    assert backup["status"] == "complete-host-backup-user-area-only"
    assert backup["user_area"] == {"bytes": CAPACITY, "sha256":
                                  "471a3b80e55c44823c601e4918504fa2977665021d8e36fcda7b79d185dc0695"}
    assert args.backup.stat().st_size == CAPACITY
    for name, expected in manifest["files"].items():
        path = args.artifacts / name
        assert path.resolve().is_relative_to(args.artifacts.resolve())
        with path.open("rb") as handle:
            assert {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(handle, "sha256").hexdigest()} == expected
    config = (args.artifacts / "linux.config").read_bytes()
    zimage = (args.artifacts / "zImage").read_bytes()
    identity = hashlib.sha256(config + zimage).hexdigest()
    version = "6.12.112~" + identity[:32] + "-r1"
    settings = json.loads(args.settings.read_bytes())
    arguments = ["ssh", "-b", settings["source"], "-i", settings["private_key"],
                 "-o", "StrictHostKeyChecking=accept-new", "-o", "UserKnownHostsFile=" + settings["known_hosts"],
                 "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "root@" + settings["host"]]

    def ssh(command, data=None, timeout=30):
        result = subprocess.run([*arguments, command], input=data, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError("Remote step failed; no further write/reboot: " + result.stderr.decode(errors="replace"))
        return result.stdout

    guard = r'''set -eu
[ "$(tr -d '\000' < /proc/device-tree/compatible)" = 'tianyi,ty1208z-ca-openwrt-system-ramhi3798mv100-series' ]
[ "$(uname -r)" = 6.12.112 ]
[ "$(cat /sys/class/block/mmcblk0/size)" = 15269888 ]
[ "$(cat /sys/class/block/mmcblk0/device/name)" = 008G30 ]
[ "$(cat /sys/class/block/mmcblk0p9/start)" = 1249280 ]
[ "$(cat /sys/class/block/mmcblk0p9/size)" = 14020608 ]
[ "$(cat /sys/class/block/mmcblk0/ro)" = 0 ]
[ "$(cat /sys/class/block/mmcblk1/ro)" = 1 ]
[ "$(cat /sys/class/block/mmcblk0p9/ro)" = 1 ]
! grep -Eq '^/dev/mmcblk0(p[0-9]+)? ' /proc/mounts
[ ! -e /dev/mmcblk0boot0 ] && [ ! -e /dev/mmcblk0rpmb ]
apk query --installed --format json kernel
'''
    installed = json.loads(ssh("sh -s", guard.encode()))
    assert len(installed) == 1 and installed[0]["version"] == version, "Exact opt-in kernel APK identity differs"
    preimage = ssh(f"dd if=/dev/mmcblk0 bs=512 skip={SECTOR} count=1 2>/dev/null")
    assert len(preimage) == 512
    args.output.mkdir(parents=True)
    preimage_path = args.output / "sector-before.PRIVATE.bin"
    with preimage_path.open("xb") as handle:
        handle.write(preimage)
        handle.flush()
        import os
        os.fsync(handle.fileno())
    pattern = hashlib.sha256(zimage + b"TY1208Z-one-sector-write-probe").digest() * 16
    assert pattern != preimage
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        for name, payload in (("before", preimage), ("pattern", pattern), ("control", control)):
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(payload), 0o700 if name == "control" else 0o600
            archive.addfile(member, io.BytesIO(payload))
    ssh("umask 077; mkdir -p /tmp/ty1208z-write-probe; tar -xf - -C /tmp/ty1208z-write-probe", data.getvalue())
    script = f'''set -eu
cd /tmp/ty1208z-write-probe
dd if=/dev/mmcblk0p9 of=current bs=512 skip={PARTITION_SECTOR} count=1 2>/dev/null
cmp before current
restore() {{
    trap - EXIT HUP INT TERM
    dd if=before of=/dev/mmcblk0p9 bs=512 seek={PARTITION_SECTOR} count=1 conv=notrunc,fsync 2>/dev/null || return 1
    ./control flush || return 1
    dd if=/dev/mmcblk0p9 of=restored bs=512 skip={PARTITION_SECTOR} count=1 2>/dev/null || return 1
    cmp before restored || return 1
    ./control lock || return 1
    [ "$(cat /sys/class/block/mmcblk0p9/ro)" = 1 ]
}}
./control unlock
[ "$(cat /sys/class/block/mmcblk0p9/ro)" = 0 ]
trap restore EXIT HUP INT TERM
dd if=pattern of=/dev/mmcblk0p9 bs=512 seek={PARTITION_SECTOR} count=1 conv=notrunc,fsync 2>/dev/null
./control flush
dd if=/dev/mmcblk0p9 of=readback bs=512 skip={PARTITION_SECTOR} count=1 2>/dev/null
cmp pattern readback
restore
echo NATIVE_EMMC_WRITE_READBACK_RESTORE_PASS
'''
    receipt = {"plan": plan, "started_utc": datetime.now(timezone.utc).isoformat(),
               "preimage_sha256": hashlib.sha256(preimage).hexdigest(), "kernel_identity": identity,
               "status": "write-starting-not-yet-accepted", "private_preimage": preimage_path.name}
    receipt_path = args.output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    output = ssh("sh -s", script.encode(), timeout=45)
    (args.output / "result.PRIVATE.log").write_bytes(output)
    assert b"NATIVE_EMMC_WRITE_READBACK_RESTORE_PASS\n" in output
    receipt.update(status="one-sector-write-readback-restored", ended_utc=datetime.now(timezone.utc).isoformat())
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "bytes": 512, "original_restored": True}))


if __name__ == "__main__":
    main()
