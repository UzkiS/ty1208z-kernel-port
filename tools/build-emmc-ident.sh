#!/bin/bash
# Separate restricted card-identification RAM image, without block devices.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
profile=${2:-ident}
case "$profile" in ident|read) ;; *) echo 'Unknown restricted MMC profile' >&2; exit 1 ;; esac
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-emmc-$profile"
artifacts="$project/artifacts/emmc-${profile}1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
if [ ! -f "$diagnostic/.config" ] || [ ! -f "$diagnostic/initramfs.cpio" ]; then
    echo 'Run make build first; identification reuses diagnostic RAM userspace.' >&2
    exit 1
fi
python3 "$project/tools/test_emmc_ident.py" --linuxsrc "$linuxsrc"
python3 "$project/tools/test_emmc_handoff.py" --linuxsrc "$linuxsrc"
mkdir -p "$kout" "$artifacts/checks"
cp "$diagnostic/.config" "$kout/.config"
cp "$diagnostic/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-emmc-$profile.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
for option in MMC MMC_DW MMC_DW_PLTFM MMC_DW_HI3798MV100_IDENT; do
    grep -qx "CONFIG_${option}=y" "$kout/.config"
done
for option in BLOCK MMC_BLOCK MMC_TEST NET USB_SUPPORT MTD MODULES SMP DEBUG_FS \
    PWRSEQ_EMMC PWRSEQ_SIMPLE HI3798MV100_EMMC_AUDIT; do
    if grep -qE "^CONFIG_${option}=[ym]$" "$kout/.config"; then
        echo "Prohibited subsystem: CONFIG_${option}" >&2
        exit 1
    fi
done
if [ "$profile" = read ]; then
    grep -qx 'CONFIG_HI3798MV100_EMMC_READ_SAMPLES=y' "$kout/.config"
    python3 "$project/tools/test_emmc_samples.py" --linuxsrc "$linuxsrc"
fi
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-16}" zImage "hisilicon/hi3798mv100-ty1208z-emmc-$profile.dtb"
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-emmc-$profile.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n "TY1208Z eMMC $profile diagnostic" -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config initramfs.cpio sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_emmc_profiles.py"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo "EMMC $profile BUILT; hardware untested, no block devices/card writes/settings."
