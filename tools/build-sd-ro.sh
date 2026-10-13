#!/bin/bash
# Independent, enforced read-only SDHC/SDXC block/filesystem RAM candidate.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-sd-ro"
rootfs="$taskbase/build/initramfs-sd-ro"
artifacts="$project/artifacts/sd-ro1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
mkdir -p "$kout" "$rootfs" "$artifacts/checks"
cp -a "$taskbase/build/initramfs-root/." "$rootfs/"
install -m 755 "$project/initramfs/sd-diag" "$rootfs/bin/sd-diag"
install -m 755 "$project/initramfs/sd-ro-diag" "$rootfs/bin/sd-ro-diag"
qemu-arm "$rootfs/bin/busybox" sh -n "$project/initramfs/sd-ro-diag"
"${cross}gcc" -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfpu=neon -mfloat-abi=hard "$project/tools/sd-ro-probe.c" -o "$rootfs/bin/sd-ro-probe"
python3 "$project/tools/make_initramfs.py" "$rootfs" "$artifacts/initramfs.cpio"
cp "$artifacts/initramfs.cpio" "$kout/initramfs.cpio"
cp "$diagnostic/.config" "$kout/.config"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-sd-ro.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
python3 "$project/tools/test_sd_ident.py" --linuxsrc "$linuxsrc"
python3 "$project/tools/test_sd_ident_driver.py" --linuxsrc "$linuxsrc"
python3 "$project/tools/test_sd_ro.py" --linuxsrc "$linuxsrc"
python3 "$project/tools/test_sd_restart.py"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-16}" zImage hisilicon/hi3798mv100-ty1208z-sd-ro.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-sd-ro.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z SD read-only filesystem' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
cp "$rootfs/bin/sd-ro-probe" "$artifacts/sd-ro-probe.armhf"
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_sd_ro_profile.py" --artifacts "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo 'SD READ-ONLY BUILT; hardware untested, no card writes/settings or persistent installation.'
