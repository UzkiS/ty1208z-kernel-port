#!/bin/bash
# Independent host0 enumeration image following the physical capability audit.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=$(realpath -m -- "${1:-"$project/.work"}")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-usb-host"
rootfs="$taskbase/build/usb-host-root"
artifacts="$project/artifacts/usb-host1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
for name in clk-ty1208z-usb.c ty1208z-usb-host0.h; do
    cmp "$project/overlay/drivers/clk/hisilicon/$name" "$linuxsrc/drivers/clk/hisilicon/$name"
done
python3 "$project/tools/fetch_references.py"
python3 "$project/tools/test_usb_host0.py"
mkdir -p "$kout" "$rootfs"/{bin,sbin,dev,proc,sys,tmp,etc} "$artifacts/checks"
install -m 755 "$project/artifacts/diag1/busybox.armhf" "$rootfs/bin/busybox"
install -m 755 "$project/initramfs/init" "$rootfs/init"
install -m 755 "$project/initramfs/diag" "$rootfs/bin/diag"
install -m 755 "$project/initramfs/usb-diag" "$rootfs/bin/usb-diag"
install -m 755 "$project/artifacts/diag1/time64-probe.armhf" "$rootfs/bin/time64-probe"
ln -sf busybox "$rootfs/bin/sh"
python3 "$project/tools/make_initramfs.py" "$rootfs" "$artifacts/initramfs.cpio"
cp "$diagnostic/.config" "$kout/.config"
cp "$artifacts/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-usb-host.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" -j"${JOBS:-16}" \
    zImage hisilicon/hi3798mv100-ty1208z-usb-host.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-usb-host.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z USB host0 OFFLINE' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_usb_host_profile.py" --artifacts "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
grep -q '^USB_HOST0_OBSERVATION_COMPLETE no-class-driver no-firmware-loading' "$artifacts/checks/qemu-virt-boot.log"
if grep -q 'USB_HOST0_OBSERVER_FAIL' "$artifacts/checks/qemu-virt-boot.log"; then
    echo 'USB observer failed under actual ARM shell.' >&2
    exit 1
fi
echo 'USB HOST0 ENUMERATION CANDIDATE; no class driver, Wi-Fi firmware or radio acceptance.'
