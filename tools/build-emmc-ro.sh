#!/bin/bash
# Independent RAM-root experiment; only measured eMMC user-area reads.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-emmc-ro"
rootfs="$taskbase/build/initramfs-emmc-ro"
artifacts="$project/artifacts/emmc-ro1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
mkdir -p "$kout" "$rootfs" "$artifacts/checks"
cp -a "$taskbase/build/initramfs-root/." "$rootfs/"
install -m 755 "$project/initramfs/emmc-ro-diag" "$rootfs/bin/emmc-ro-diag"
qemu-arm "$rootfs/bin/busybox" sh -n "$project/initramfs/emmc-ro-diag"
python3 "$project/tools/test_emmc_ro_guest.py" --busybox "$rootfs/bin/busybox" | tee "$artifacts/checks/actual-guest.log"
"${cross}gcc" -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfpu=neon -mfloat-abi=hard "$project/tools/emmc-ro-probe.c" -o "$rootfs/bin/emmc-ro-probe"
"${cross}readelf" -h -A -l "$rootfs/bin/emmc-ro-probe" > "$artifacts/checks/elf-emmc-ro-probe.txt"
if grep -q INTERP "$artifacts/checks/elf-emmc-ro-probe.txt"; then
    echo 'eMMC read-only probe must be static.' >&2; exit 1
fi
python3 "$project/tools/make_initramfs.py" "$rootfs" "$artifacts/initramfs.cpio"
cp "$artifacts/initramfs.cpio" "$kout/initramfs.cpio"
cp "$diagnostic/.config" "$kout/.config"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-emmc-ro.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
python3 "$project/tools/test_emmc_ro.py" --linuxsrc "$linuxsrc" | tee "$artifacts/checks/actual-policy.log"
python3 "$project/tools/test_emmc_ro_driver.py" --linuxsrc "$linuxsrc" | tee "$artifacts/checks/actual-shutdown.log"
python3 "$project/tools/test_emmc_ro_restart.py" | tee "$artifacts/checks/actual-restart.log"
python3 "$project/tools/test_emmc_ro_probe.py" | tee "$artifacts/checks/actual-userspace.log"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-12}" zImage hisilicon/hi3798mv100-ty1208z-emmc-ro.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-emmc-ro.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z eMMC user-area RO' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
cp "$rootfs/bin/emmc-ro-probe" "$artifacts/emmc-ro-probe.armhf"
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_emmc_ro_profile.py" --artifacts "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo 'EMMC USER-AREA RO BUILT; hardware untested, no card writes/settings or persistent installation.'
