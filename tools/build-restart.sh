#!/bin/bash
# Isolated SP805 restart RAM experiment; no watchdog device/storage/network.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-restart"
artifacts="$project/artifacts/restart1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
mkdir -p "$kout" "$artifacts/checks"
cp "$diagnostic/.config" "$kout/.config"
cp "$diagnostic/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-restart.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
grep -qx 'CONFIG_POWER_RESET_TY1208Z_SP805=y' "$kout/.config"
for prohibited in WATCHDOG USB_SUPPORT NET BLOCK MMC MTD ATA SCSI MODULES SMP DEBUG_FS; do
    if grep -qE "^CONFIG_${prohibited}=[ym]$" "$kout/.config"; then
        echo "Prohibited subsystem: CONFIG_${prohibited}" >&2
        exit 1
    fi
done
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-16}" zImage hisilicon/hi3798mv100-ty1208z-restart.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-restart.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z SP805 restart experiment' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config initramfs.cpio sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_restart.py" --artifacts "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo 'SP805 RESTART BUILT; hardware untested; startup has no writes; only explicit restart arms reset.'
