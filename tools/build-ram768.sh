#!/bin/bash
# Separate low-768-MiB memory test, with no storage/network/USB or modules.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-ram768"
rootfs="$taskbase/build/initramfs-ram768"
artifacts="$project/artifacts/ram768"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
mkdir -p "$kout" "$rootfs" "$artifacts/checks"
cp -a "$taskbase/build/initramfs-root/." "$rootfs/"
install -m 755 "$project/initramfs/ram768-diag" "$rootfs/bin/ram768-diag"
qemu-arm "$rootfs/bin/busybox" sh -n "$project/initramfs/ram768-diag"
"${cross}gcc" -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfpu=neon -mfloat-abi=hard "$project/tools/ram768-probe.c" -o "$rootfs/bin/ram768-probe"
python3 "$project/tools/make_initramfs.py" "$rootfs" "$artifacts/initramfs.cpio"
cp "$artifacts/initramfs.cpio" "$kout/initramfs.cpio"
cp "$diagnostic/.config" "$kout/.config"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-ram768.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
python3 "$project/tools/test_ram768.py" --linuxsrc "$linuxsrc"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-16}" zImage hisilicon/hi3798mv100-ty1208z-ram768.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-ram768.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z bounded 768MiB RAM' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
cp "$rootfs/bin/ram768-probe" "$artifacts/ram768-probe.armhf"
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_ram768.py" --artifacts "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
for marker in 'RAM768_MOUNT_READY tmpfs' 'RAM768_MEMORY_REFUSED insufficient-available-RAM' 'RAM768_QEMU_LOW_MEMORY_DENIAL_PASS'; do
    grep -q "$marker" "$artifacts/checks/qemu-virt-boot.log"
done
if grep -q RAM768_QEMU_LOW_MEMORY_DENIAL_FAIL "$artifacts/checks/qemu-virt-boot.log"; then
    echo 'Actual ARM mount/low-memory cleanup failed.' >&2
    exit 1
fi
echo 'RAM768_ACTUAL_ARM_MOUNT_LOW_MEMORY_DENIAL_PASS no file allocation, mount removed'
echo 'RAM768 BUILT; hardware untested; physical memory stress requires fresh allocation-table evidence.'
