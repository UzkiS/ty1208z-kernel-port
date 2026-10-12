#!/bin/bash
# Separate Ethernet profiles; no PHY/reset/DMA or persistent writes.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
mode=${2:-audit}
case "$mode" in
    audit) profile=ethernet-audit; option=HI3798MV100_ETHERNET_AUDIT
        other=HI3798MV100_ETHERNET_CLOCK_ID; test_script=test_ethernet_audit.py ;;
    clock-id) profile=ethernet-clock-id; option=HI3798MV100_ETHERNET_CLOCK_ID
        other=HI3798MV100_ETHERNET_AUDIT; test_script=test_ethernet_clock_id.py ;;
    *) echo 'Expected audit or clock-id profile' >&2; exit 1 ;;
esac
kout="$taskbase/build/linux-$profile"
artifacts="$project/artifacts/${profile}1"
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
python3 "$project/tools/$test_script"
mkdir -p "$kout" "$artifacts/checks"
cp "$diagnostic/.config" "$kout/.config"
cp "$diagnostic/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-$profile.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
grep -qx "CONFIG_${option}=y" "$kout/.config"
for prohibited in BLOCK MMC NET USB_SUPPORT MTD MODULES SMP HI3798MV100_EMMC_AUDIT DEBUG_FS "$other"; do
    if grep -qE "^CONFIG_${prohibited}=[ym]$" "$kout/.config"; then
        echo "Prohibited subsystem: CONFIG_${prohibited}" >&2
        exit 1
    fi
done
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-16}" zImage "hisilicon/hi3798mv100-ty1208z-$profile.dtb"
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-$profile.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n "TY1208Z $profile" -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
for name in busybox.armhf time64-probe.armhf busybox.config initramfs.cpio sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo "ETHERNET ${mode} BUILT; hardware untested, fixed state guards checked."
