#!/bin/bash
# Separate inherited-PHY network experiment; no storage drivers or board access.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
bbsource="$taskbase/src/busybox-1.37.0"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-ethernet-net"
bout="$taskbase/build/busybox-ethernet-net"
rootfs="$taskbase/build/ethernet-net-root"
artifacts="$project/artifacts/ethernet-net1"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
python3 "$project/tools/test_ethernet_net.py"
python3 "$project/tools/test_femac_datapath.py" --linux "$linuxsrc"
mkdir -p "$kout" "$bout" "$rootfs"/{bin,sbin,dev,proc,sys,tmp,etc} "$artifacts/checks"
make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" allnoconfig
python3 "$project/tools/merge_fragment.py" "$bout/.config" "$project/config/busybox-diagnostic.fragment"
python3 "$project/tools/merge_fragment.py" "$bout/.config" "$project/config/busybox-ethernet.fragment"
set +o pipefail
yes '' | make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" oldconfig
configstatus=${PIPESTATUS[1]}
set -o pipefail
test "$configstatus" -eq 0
make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" silentoldconfig
make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" -j"${JOBS:-16}"
install -m 755 "$bout/busybox" "$rootfs/bin/busybox"
install -m 755 "$project/initramfs/init" "$rootfs/init"
install -m 755 "$project/initramfs/diag" "$rootfs/bin/diag"
install -m 755 "$project/initramfs/ethernet-diag" "$rootfs/bin/ethernet-diag"
install -m 755 "$project/initramfs/ethernet-dhcp" "$rootfs/bin/ethernet-dhcp"
install -m 755 "$project/artifacts/diag1/time64-probe.armhf" "$rootfs/bin/time64-probe"
ln -sf busybox "$rootfs/bin/sh"
python3 "$project/tools/make_initramfs.py" "$rootfs" "$artifacts/initramfs.cpio"
cp "$diagnostic/.config" "$kout/.config"
cp "$artifacts/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-ethernet-net.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"${JOBS:-16}" zImage hisilicon/hi3798mv100-ty1208z-ethernet-net.dtb
cp "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
cp "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-ethernet-net.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'TY1208Z inherited Ethernet' -d "$artifacts/zImage-appended-dtb" "$artifacts/uImage-UNTESTED.bin"
cp "$kout/.config" "$artifacts/linux.config"
cp "$bout/.config" "$artifacts/busybox.config"
cp "$bout/busybox" "$artifacts/busybox.armhf"
for name in time64-probe.armhf sources.lock.json; do
    cp "$project/artifacts/diag1/$name" "$artifacts/"
done
python3 "$project/tools/inspect_kernel_layout.py" --build "$kout" --output "$artifacts/checks/kernel-layout.json"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
python3 "$project/tools/test_ethernet_net.py" --artifacts "$artifacts"
bash "$project/tools/test-qemu.sh" "$artifacts"
echo 'ETHERNET NETWORK CANDIDATE BUILT: inherited PHY only; hardware traffic untested.'
