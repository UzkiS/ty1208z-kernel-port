#!/usr/bin/env python3
"""Run official ARM sysupgrade --test with synthetic storage facts and no disks."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from native_upgrade import PROJECT, digest

GUEST = r'''#!/bin/sh
set -e
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mkdir -p /realproc
mount -t proc proc /realproc
mount -t sysfs sysfs /sys
grep -q 'linux,dummy-virt' /sys/firmware/devicetree/base/compatible
umount /sys
# Synthetic read-only facts for the validation boundary. No block device exists.
mkdir -p /sys/firmware/devicetree/base /sys/class/block/mmcblk0/device
printf 'tianyi,ty1208z-ca-openwrt-system-ram\000hi3798mv100-series\000' > /sys/firmware/devicetree/base/compatible
echo MMC > /sys/class/block/mmcblk0/device/type
echo 008G30 > /sys/class/block/mmcblk0/device/name
echo 15269888 > /sys/class/block/mmcblk0/size
mkdir -p /sys/class/block/mmcblk0/holders /sys/class/block/mmcblk0p6/holders /sys/class/block/mmcblk0p9/holders
echo 28672 > /sys/class/block/mmcblk0p6/start
echo 40960 > /sys/class/block/mmcblk0p6/size
echo 1249280 > /sys/class/block/mmcblk0p9/start
echo 14020608 > /sys/class/block/mmcblk0p9/size
echo '/dev/mmcblk0p9 / ext4 rw 0 0' > /proc/mounts
mkdir -p /proc/self
echo '30 20 179:9 / / rw - ext4 /dev/root rw' > /proc/self/mountinfo
mkdir -p /tmp/sysinfo
echo tianyi,ty1208z-ca-openwrt-system-ram > /tmp/sysinfo/board_name
/usr/libexec/validate_firmware_image /tmp/firmware.bin > /tmp/result.json
cat /tmp/result.json
grep -Eq '"valid":[[:space:]]*true' /tmp/result.json
echo NATIVE_UPGRADE_RPC_VALIDATION_PASS
/sbin/sysupgrade --test /tmp/firmware.bin
echo NATIVE_UPGRADE_OFFICIAL_SYSUPGRADE_TEST_PASS
# Change only the board field, retaining otherwise valid payloads.
dd if=/tmp/badmanifest of=/tmp/firmware.bin bs=1 seek=512 conv=notrunc
if /sbin/sysupgrade --force --test /tmp/firmware.bin; then
    echo NATIVE_UPGRADE_WRONG_BOARD_ACCEPTED
    exit 1
fi
echo NATIVE_UPGRADE_WRONG_BOARD_FORCE_DENIED
echo NATIVE_UPGRADE_VALIDATION_QEMU_PASS
/bin/busybox poweroff -f
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True, help="Previously accepted QEMU-only kernel")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Inspect existing evidence instead of overwriting it"
    args.output.mkdir(parents=True)
    root = args.output / "root"
    shutil.copytree(args.delivery / "root", root, symlinks=True)
    # Applications are unchanged and not part of this check. Keep their real
    # compressed upgrade payload, but omit executable duplicates from the guest.
    for name in ("usr/lib/docker/cli-plugins/docker-compose", "usr/sbin/runc",
                 "usr/bin/containerd-shim-runc-v2", "usr/bin/ctr", "usr/bin/sing-box", "usr/bin/xray",
                 "usr/bin/docker", "usr/bin/containerd-stress", "usr/bin/containerd", "usr/bin/dockerd"):
        (root / name).unlink()
    receipt = json.loads((args.delivery / "manifest.json").read_bytes())
    image = args.delivery / receipt["image"]["file"]
    assert digest(image) == receipt["image"]["sha256"]
    (root / "tmp").mkdir(exist_ok=True)
    shutil.copyfile(image, root / "tmp/firmware.bin")
    with tarfile.open(image) as source:
        manifest = source.extractfile("manifest").read()
    bad = manifest.replace(b'tianyi,ty1208z-ca"', b'tianyi,ty1208x-ca"')
    assert bad != manifest and len(bad) == len(manifest)
    (root / "tmp/badmanifest").write_bytes(bad)
    # The guest has no disks, so df capacity is also explicitly synthetic.
    df = root / "bin/df"
    df.unlink()
    df.write_text('#!/bin/sh\nprintf "Filesystem 1K-blocks Used Available Use%% Mounted on\\nsynthetic 8388608 1024 8387584 1%% /\\n"\n')
    df.chmod(0o755)
    init = root / "upgrade-validation-init"
    init.write_text(GUEST)
    init.chmod(0o755)
    cpio = args.output / "rootfs.cpio"
    subprocess.run([sys.executable, str(PROJECT / "tools/make_initramfs.py"), str(root), str(cpio)], check=True)
    packed = args.output / "rootfs.cpio.gz"
    with cpio.open("rb") as source, packed.open("wb") as target:
        with gzip.GzipFile(filename="", fileobj=target, mode="wb", compresslevel=1, mtime=0) as handle:
            shutil.copyfileobj(source, handle)
    command = ["qemu-system-arm", "-machine", "virt,gic-version=2", "-cpu", "cortex-a7", "-m", "768M",
               "-smp", "1", "-nographic", "-monitor", "none", "-serial", "stdio", "-nic", "none",
               "-no-reboot", "-kernel", str(args.kernel), "-initrd", str(packed),
               "-append", "console=ttyAMA0 rdinit=/upgrade-validation-init panic=0"]
    log = args.output / "qemu.log"
    with log.open("wb") as handle:
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, timeout=240)
    transcript = log.read_text(errors="replace")
    markers = ["NATIVE_UPGRADE_RPC_VALIDATION_PASS", "NATIVE_UPGRADE_OFFICIAL_SYSUPGRADE_TEST_PASS",
               "NATIVE_UPGRADE_WRONG_BOARD_FORCE_DENIED", "NATIVE_UPGRADE_VALIDATION_QEMU_PASS"]
    assert result.returncode == 0 and all(marker in transcript for marker in markers), transcript[-6000:]
    report = {"status": "official ARM sysupgrade validation passed in QEMU",
              "markers": markers, "image_sha256": receipt["image"]["sha256"],
              "kernel_sha256": digest(args.kernel), "console_sha256": digest(log),
              "guest_sha256": digest(init), "disks": False, "network": False,
              "synthetic_facts": ["board identity", "partition layout", "mount table", "free space"],
              "not_established": ["physical upgrade", "RAM pivot/unmount", "eMMC activation/readback/reboot"]}
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
