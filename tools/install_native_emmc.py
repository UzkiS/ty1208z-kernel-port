#!/usr/bin/env python3
"""Plan a fixed p6/p9 installation or recovery; apply only with session authorization."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

CAPACITY = 7818182656
ROOT_BYTES = 7178551296
BACKUP_SHA = "471a3b80e55c44823c601e4918504fa2977665021d8e36fcda7b79d185dc0695"


def checked(path, expected):
    with path.open("rb") as handle:
        assert {"bytes": path.stat().st_size,
                "sha256": hashlib.file_digest(handle, "sha256").hexdigest()} == expected, path.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk", type=Path, required=True)
    parser.add_argument("--ram", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--probe-receipt", type=Path, required=True)
    parser.add_argument("--mode", choices=("install", "restore"), default="install")
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true", help="Requires separate full p6/p9 installation/recovery authorization")
    args = parser.parse_args()
    disk = json.loads((args.disk / "manifest.json").read_bytes())
    ram = json.loads((args.ram / "manifest.json").read_bytes())
    control = json.loads((args.control / "manifest.json").read_bytes())
    recovery = json.loads((args.recovery / "manifest.json").read_bytes())
    backup = json.loads(Path(str(args.backup) + ".json").read_bytes())
    probe = json.loads(args.probe_receipt.read_bytes())
    assert probe["status"] == "one-sector-write-readback-restored"
    assert probe["plan"]["bytes"] == 512 and probe["plan"]["user_area_sector"] == 15269887
    assert backup["status"] == "complete-host-backup-user-area-only"
    assert backup["user_area"] == {"bytes": CAPACITY, "sha256": BACKUP_SHA}
    assert args.backup.stat().st_size == CAPACITY
    assert disk["partitions"] == {"p6": {"offset_bytes": 14680064, "bytes": 20971520},
                                  "p9": {"offset_bytes": 639631360, "bytes": ROOT_BYTES}}
    assert ram["persistent_candidate"] is True
    assert disk["kernel_build"] == ram["files"]["checks/kernel-build.json"]
    for name in ("kernel-p6-INSTALL-UNTESTED.bin", "rootfs-p9.ext4.gz", "disk-root.dtb"):
        checked(args.disk / name, disk["files"][name])
    for name in ("linux.config", "zImage", "checks/kernel-build.json"):
        checked(args.ram / name, ram["files"][name])
    checked(args.control / control["file"], {"bytes": control["bytes"], "sha256": control["sha256"]})
    checked(args.recovery / recovery["p6"]["file"], {key: recovery["p6"][key] for key in ("bytes", "sha256")})
    assert recovery["p9"]["offset_bytes"] == 639631360 and recovery["p9"]["bytes"] == ROOT_BYTES
    assert recovery["p9"]["whole_backup"] == backup["user_area"]
    zimage = (args.ram / "zImage").read_bytes()
    kernel = (args.disk / "kernel-p6-INSTALL-UNTESTED.bin").read_bytes()
    assert kernel[64:] == zimage + (args.disk / "disk-root.dtb").read_bytes()
    identity = hashlib.sha256((args.ram / "linux.config").read_bytes() + zimage).hexdigest()
    if args.mode == "restore":
        kernel = (args.recovery / recovery["p6"]["file"]).read_bytes()
    kernel += bytes(-len(kernel) % 512)
    kernel_sha = hashlib.sha256(kernel).hexdigest()
    assert 0 < len(kernel) <= 20971520
    plan = {"mode": args.mode, "requires_separate_full_partition_write_authorization": True,
            "write_order": ["p9", "p6"], "p9_bytes": ROOT_BYTES, "p6_bytes": len(kernel),
            "p9_sha256": disk["files"]["rootfs-p9.ext4"]["sha256"] if args.mode == "install" else "computed from the backed-up p9 range while streaming",
            "p6_padded_sha256": kernel_sha, "backup_user_area_sha256": BACKUP_SHA,
            "verification": "fsync, discard block cache, SHA-256 readback, lock each partition readonly",
            "persistent_boot_environment_changes": False, "automatic_reboot": False,
            "failure": "retain receipt/logs; no further write or reboot; separately invoke prepared recovery within authorized scope",
            "untouched": "p1-p5/p7-p8, fastboot, SD, boot0/boot1/RPMB and security state"}
    if not args.apply:
        print(json.dumps(plan, indent=2))
        return
    assert args.settings and args.output and not args.output.exists()
    # Revalidate the retained recovery bytes before any destructive operation.
    checked(args.backup, backup["user_area"])
    settings = json.loads(args.settings.read_bytes())
    ssh_args = ["ssh", "-b", settings["source"], "-i", settings["private_key"],
                "-o", "StrictHostKeyChecking=accept-new", "-o", "UserKnownHostsFile=" + settings["known_hosts"],
                "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=10",
                "-o", "ServerAliveCountMax=3", "root@" + settings["host"]]

    def ssh(command, data=None):
        result = subprocess.run([*ssh_args, command], input=data, capture_output=True, timeout=30)
        assert result.returncode == 0, "Pre-write RAM setup/guard failed"
        return result.stdout

    guard = r'''set -eu
[ "$(tr -d '\000' < /proc/device-tree/compatible)" = 'tianyi,ty1208z-ca-openwrt-system-ramhi3798mv100-series' ]
[ "$(uname -r)" = 6.12.112 ]
[ "$(cat /sys/class/block/mmcblk0/device/name)" = 008G30 ]
[ "$(cat /sys/class/block/mmcblk0/size)" = 15269888 ]
[ "$(cat /sys/class/block/mmcblk0/ro)" = 0 ]
[ "$(cat /sys/class/block/mmcblk1/ro)" = 1 ]
[ "$(cat /sys/class/block/mmcblk0p6/start)" = 28672 ]
[ "$(cat /sys/class/block/mmcblk0p6/size)" = 40960 ]
[ "$(cat /sys/class/block/mmcblk0p9/start)" = 1249280 ]
[ "$(cat /sys/class/block/mmcblk0p9/size)" = 14020608 ]
for p in /sys/class/block/mmcblk0p*/ro; do [ "$(cat "$p")" = 1 ]; done
! grep -Eq '^[^ ]+ [^ ]+ 179:' /proc/self/mountinfo
! grep -q mmcblk /proc/swaps
[ ! -e /dev/mmcblk0boot0 ] && [ ! -e /dev/mmcblk0boot1 ] && [ ! -e /dev/mmcblk0rpmb ]
apk query --installed --format json kernel
'''
    installed = json.loads(ssh("sh -s", guard.encode()))
    assert len(installed) == 1 and installed[0]["version"] == "6.12.112~" + identity[:32] + "-r1"
    args.output.mkdir(parents=True)
    receipt_path = args.output / "receipt.json"
    receipt = {"status": "p6-p9-operation-starting-incomplete", "plan": plan, "kernel_identity": identity,
               "started_utc": datetime.now(timezone.utc).isoformat(), "completed": []}

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    save()
    ssh("umask 077; mkdir -p /tmp/ty1208z-install; cat > /tmp/ty1208z-install/control",
        (args.control / control["file"]).read_bytes())
    ssh("chmod 700 /tmp/ty1208z-install/control")

    def transfer(partition, size, source, *, compressed=False, expected=None):
        assert partition in ("p6", "p9") and size % 512 == 0
        read_block = 1048576 if size % 1048576 == 0 else 512
        command = f'''set -eu; set -o pipefail
cd /tmp/ty1208z-install
./control {partition} unlock
trap './control {partition} lock' EXIT HUP INT TERM
gzip -dc | dd of=/dev/mmcblk0{partition} bs=1048576 conv=notrunc,fsync
./control {partition} flush
sum=$(dd if=/dev/mmcblk0{partition} bs={read_block} count={size // read_block} 2>/dev/null | sha256sum)
./control {partition} lock
[ "$(cat /sys/class/block/mmcblk0{partition}/ro)" = 1 ]
trap - EXIT HUP INT TERM
echo TY1208Z_{partition.upper()}_SHA256=${{sum%% *}}
'''
        log = args.output / (partition + ".PRIVATE.log")
        digest = hashlib.sha256()
        with log.open("xb") as output:
            process = subprocess.Popen([*ssh_args, command], stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
            try:
                if compressed:
                    while data := source.read(1024 * 1024):
                        process.stdin.write(data)
                else:
                    remaining = size
                    with gzip.GzipFile(filename="", fileobj=process.stdin, mode="wb", compresslevel=1, mtime=0) as archive:
                        while remaining:
                            data = source.read(min(1024 * 1024, remaining))
                            assert data, "Source ended before the fixed partition range"
                            digest.update(data)
                            archive.write(data)
                            remaining -= len(data)
                process.stdin.close()
                result = process.wait()
            except BaseException:
                # Closing SSH ends its remote shell; its trap attempts a readonly
                # lock. Never claim restoration or schedule another write/reset.
                process.stdin.close()
                process.wait()
                raise
        assert result == 0, "Write/readback failed; inspect private log, no reboot"
        expected = expected or digest.hexdigest()
        match = re.search(rb"(?:^|\n)TY1208Z_" + partition.upper().encode() + rb"_SHA256=([0-9a-f]{64})\s*$", log.read_bytes())
        assert match and match[1].decode() == expected, "Physical readback differs; no further write/reboot"
        receipt["completed"].append({"partition": partition, "bytes": size, "sha256": expected, "readonly_locked": True})
        save()
        print(partition + " written, cache-cleared SHA-256 readback matched, readonly locked", flush=True)

    if args.mode == "install":
        with (args.disk / "rootfs-p9.ext4.gz").open("rb") as source:
            transfer("p9", ROOT_BYTES, source, compressed=True, expected=disk["files"]["rootfs-p9.ext4"]["sha256"])
    else:
        with args.backup.open("rb") as source:
            source.seek(639631360)
            transfer("p9", ROOT_BYTES, source)
    transfer("p6", len(kernel), io.BytesIO(kernel), expected=kernel_sha)
    receipt.update(status="p6-p9-written-verified-awaiting-disk-root-boot" if args.mode == "install" else "original-p6-p9-restored-readback-verified",
                   ended_utc=datetime.now(timezone.utc).isoformat())
    save()
    print(receipt["status"], flush=True)


if __name__ == "__main__":
    main()
