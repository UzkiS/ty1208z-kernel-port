#!/bin/bash
# Separate bounded host0 clock/PHY experiment; no host stack or device transfers.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=$(realpath -m -- "${1:-$project/.work}")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-usb-clock-audit"
artifacts="$project/artifacts/usb-clock-audit1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
python3 "$project/tools/test_usb_host0.py"
python3 "$project/tools/test_usb_clock_audit.py"
mkdir -p "$kout" "$artifacts/checks"
cp "$diagnostic/.config" "$kout/.config"
cp "$diagnostic/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-usb-clock-audit.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
grep -qx 'CONFIG_HI3798MV100_USB_CLOCK_AUDIT=y' "$kout/.config"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" -j"${JOBS:-16}" \
    zImage hisilicon/hi3798mv100-ty1208z-usb-clock-audit.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-usb-clock-audit.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z USB clock audit' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config initramfs.cpio sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_usb_clock_audit.py" --artifacts "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo 'USB CLOCK AUDIT BUILT; hardware untested; volatile PHY programming, SDK shutdown, no device transactions.'
