#!/bin/bash
# Simulation of virt only: does not emulate TY1208Z peripherals/secure boot.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
artifacts="$project/artifacts/diag1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
mkdir -p "$artifacts/checks"
"${cross}readelf" -h -A "$artifacts/time64-probe.armhf" > "$artifacts/checks/elf-probe.txt"
"${cross}readelf" -h -A "$artifacts/busybox.armhf" > "$artifacts/checks/elf-busybox.txt"
for name in time64-probe.armhf busybox.armhf; do
    "${cross}readelf" -l "$artifacts/$name" > "$artifacts/checks/$name.program-headers.txt"
    if grep -q INTERP "$artifacts/checks/$name.program-headers.txt"; then
        echo "Unexpected dynamic loader in $name" >&2
        exit 1
    fi
done
qemu-arm "$artifacts/time64-probe.armhf" > "$artifacts/checks/qemu-user-time64.txt"
qemu-arm "$artifacts/busybox.armhf" sh -c 'echo BUSYBOX_ARMHF_SHELL_PASS' > "$artifacts/checks/qemu-user-busybox.txt"

# Boot the SAME raw zImage and initramfs, using virt's DTB rather than MV100's.
# No host filesystems, virtual disks or network are attached.
timeout 45s qemu-system-arm -machine virt,gic-version=2 -cpu cortex-a7 \
    -m 256M -smp 1 -nographic -monitor none -serial stdio -no-reboot -nic none \
    -kernel "$artifacts/zImage" \
    -append 'console=ttyAMA0 rdinit=/init ty1208z.qemu_selftest=1' \
    > "$artifacts/checks/qemu-virt-boot.log" 2>&1
grep -q 'QEMU_INITRAMFS_TIME64_PASS' "$artifacts/checks/qemu-virt-boot.log"
if grep -qE 'TIME64_FAIL|QEMU_INITRAMFS_TIME64_FAIL|Kernel panic' "$artifacts/checks/qemu-virt-boot.log"; then
    echo 'QEMU regression failed; see boot log.' >&2
    exit 1
fi
echo 'QEMU VIRT PASS: raw kernel, initramfs, ARM shell, 2040 clock set/read and BusyBox/file timestamps.'
echo 'MV100 hardware driver, UART clock, RAM map and high-security authentication were NOT tested.'
