#!/bin/bash
# Separate RAM image; no MMC driver or card command is enabled.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-emmc-audit"
artifacts="$project/artifacts/emmc-audit1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
if [ ! -f "$diagnostic/.config" ] || [ ! -f "$diagnostic/initramfs.cpio" ]; then
    echo 'Run make build first; audit reuses the diagnostic RAM userspace.' >&2
    exit 1
fi
mkdir -p "$kout" "$artifacts/checks"
cp "$diagnostic/.config" "$kout/.config"
cp "$diagnostic/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-emmc-audit.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
grep -qx 'CONFIG_HI3798MV100_EMMC_AUDIT=y' "$kout/.config"
for option in BLOCK MMC NET USB_SUPPORT MTD MODULES SMP; do
    if grep -qE "^CONFIG_${option}=[ym]$" "$kout/.config"; then
        echo "Prohibited subsystem: CONFIG_${option}" >&2
        exit 1
    fi
done
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-16}" zImage hisilicon/hi3798mv100-ty1208z-emmc-audit.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
# Common artifact names let the measured RAM gate validate either profile.
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-emmc-audit.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z eMMC register audit' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config initramfs.cpio sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo 'EMMC REGISTER AUDIT BUILT; hardware untested, no MMC commands or clock/reset writes.'
