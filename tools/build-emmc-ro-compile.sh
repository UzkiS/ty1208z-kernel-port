#!/bin/bash
# Compile the isolated RO path; no RAM boot image or hardware acceptance.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-emmc-ro-policy"
artifacts="$project/artifacts/emmc-ro-compile"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
mkdir -p "$kout" "$artifacts/checks"
python3 "$project/tools/test_emmc_ro.py" --linuxsrc "$linuxsrc" | tee "$artifacts/checks/actual-policy.log"
cp "$diagnostic/.config" "$kout/.config"
cp "$diagnostic/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-emmc-ro.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
for option in MMC MMC_BLOCK MMC_DW MMC_DW_PLTFM MMC_DW_HI3798MV100_IDENT HI3798MV100_EMMC_READ_ONLY BLOCK; do
    grep -qx "CONFIG_${option}=y" "$kout/.config"
done
for option in HI3798MV100_EMMC_READ_SAMPLES MMC_TEST NET MODULES SMP USB_SUPPORT MTD DEBUG_FS PM; do
    if grep -qE "^CONFIG_${option}=[ym]$" "$kout/.config"; then
        echo "Prohibited eMMC RO compile subsystem: $option" >&2
        exit 1
    fi
done
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" -j"${JOBS:-12}" drivers/mmc/host/ drivers/mmc/core/
cp "$kout/.config" "$artifacts/linux.config"
for object in host/dw_mmc.o host/dw_mmc-hi3798mv100-ident.o core/block.o; do
    cp "$kout/drivers/mmc/$object" "$artifacts/"
done
python3 "$project/tools/validate_emmc_ro_compile.py" "$artifacts"
echo 'EMMC RO ARM COMPILE PASS; no boot image, filesystem/backup/restart or hardware acceptance.'
