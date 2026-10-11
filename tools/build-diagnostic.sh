#!/bin/bash
# Offline build only. Contains no device access, flashing or boot commands.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
jobs=${JOBS:-16}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
mkdir -p "$taskbase"/{downloads,src,build,logs}
linuxsrc="$taskbase/src/linux-6.12.112"
bbsource="$taskbase/src/busybox-1.37.0"
kout="$taskbase/build/linux-diagnostic"
bout="$taskbase/build/busybox-diagnostic"
rootfs="$taskbase/build/initramfs-root"
artifacts="$project/artifacts/diag1"
mkdir -p "$kout" "$bout" "$rootfs" "$artifacts/checks"

python3 - "$project" "$taskbase" <<'PY'
import hashlib, json, sys, urllib.request
from pathlib import Path
project, taskbase = map(Path, sys.argv[1:])
lock = json.loads((project / 'config/sources.lock.json').read_text())
for kind in ('linux', 'busybox'):
    item = lock[kind]
    archive = taskbase / 'downloads' / item['url'].split('/')[-1]
    if not archive.exists():
        urllib.request.urlretrieve(item['url'], archive)
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if digest != item['sha256']:
        raise SystemExit(f'{kind}: archive hash mismatch')
    print(f'{kind}: pinned archive SHA256 verified')
PY
if [ ! -d "$linuxsrc" ]; then
    tar -xf "$taskbase/downloads/linux-6.12.112.tar.xz" -C "$taskbase/src"
fi
if [ ! -d "$bbsource" ]; then
    tar -xf "$taskbase/downloads/busybox-1.37.0.tar.bz2" -C "$taskbase/src"
fi
python3 "$project/tools/make_busybox_patch.py" \
    --archive "$taskbase/downloads/busybox-1.37.0.tar.bz2" \
    --output "$project/patches/0002-busybox-stat-time64.patch"
bbpatch="$project/patches/0002-busybox-stat-time64.patch"
if patch --dry-run --silent --forward --batch -d "$bbsource" -p1 < "$bbpatch"; then
    patch --forward --batch -d "$bbsource" -p1 < "$bbpatch"
elif patch --dry-run --silent -R --batch -d "$bbsource" -p1 < "$bbpatch"; then
    echo 'Matching BusyBox patch already applied.'
else
    echo 'BusyBox source differs from pinned patch; use a fresh extraction.' >&2
    exit 1
fi
python3 "$project/tools/make_kernel_patch.py" \
    --archive "$taskbase/downloads/linux-6.12.112.tar.xz" \
    --output "$project/patches/0001-hi3798mv100-diagnostic.patch"
patchfile="$project/patches/0001-hi3798mv100-diagnostic.patch"
if patch --dry-run --silent --forward --batch -d "$linuxsrc" -p1 < "$patchfile"; then
    patch --forward --batch -d "$linuxsrc" -p1 < "$patchfile"
elif patch --dry-run --silent -R --batch -d "$linuxsrc" -p1 < "$patchfile"; then
    echo 'Matching diagnostic patch already applied.'
else
    echo 'Source tree differs from pinned patch; use a fresh extraction.' >&2
    exit 1
fi

make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" allnoconfig
python3 "$project/tools/merge_fragment.py" "$bout/.config" "$project/config/busybox-diagnostic.fragment"
# BusyBox has no Linux-style olddefconfig; defaults accept dependent options.
set +o pipefail
yes '' | make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" oldconfig
configstatus=${PIPESTATUS[1]}
set -o pipefail
[ "$configstatus" -eq 0 ]
make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" silentoldconfig
make -C "$bbsource" O="$bout" CROSS_COMPILE="$cross" -j"$jobs"
install -d "$rootfs"/{bin,sbin,dev,proc,sys,tmp,etc}
install -m 755 "$bout/busybox" "$rootfs/bin/busybox"
install -m 755 "$project/initramfs/init" "$rootfs/init"
install -m 755 "$project/initramfs/diag" "$rootfs/bin/diag"
ln -sf busybox "$rootfs/bin/sh"
"${cross}gcc" -O2 -Wall -Wextra -Werror -static -march=armv7-a \
    -mfpu=neon -mfloat-abi=hard "$project/tools/time64-probe.c" \
    -o "$rootfs/bin/time64-probe"
# cpio /dev/console must exist before /init starts; no host device node needed.
python3 "$project/tools/make_initramfs.py" "$rootfs" "$artifacts/initramfs.cpio"
install -m 644 "$artifacts/initramfs.cpio" "$kout/initramfs.cpio"

make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" allnoconfig
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-diagnostic.fragment"
"$linuxsrc/scripts/config" --file "$kout/.config" \
    --set-str INITRAMFS_SOURCE 'initramfs.cpio'
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig
# Explicitly regenerate compiled headers: WSL clock skew can leave a stale
# auto.conf from allnoconfig newer than the edited .config.
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" syncconfig
python3 "$project/tools/check_config.py" "$kout/.config" "$bout/.config" "$kout/include/config/auto.conf"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" \
    -j"$jobs" zImage hisilicon/hi3798mv100-ty1208z-diagnostic.dtb

install -m 644 "$kout/arch/arm/boot/zImage" "$artifacts/zImage"
install -m 644 "$kout/arch/arm/boot/dts/hisilicon/hi3798mv100-ty1208z-diagnostic.dtb" "$artifacts/ty1208z-diagnostic.dtb"
cat "$artifacts/zImage" "$artifacts/ty1208z-diagnostic.dtb" > "$artifacts/zImage-appended-dtb"
# These header addresses match the existing Hinas image, not a verified RAM map.
# This ordinary uImage is NOT signed or ADVCA packaged.
mkimage -A arm -O linux -T kernel -C none -a 0x02000000 -e 0x02000000 \
    -n 'Linux-6.12.112-ty1208z-diag1' -d "$artifacts/zImage-appended-dtb" \
    "$artifacts/uImage-UNTESTED.bin"
install -m 644 "$kout/.config" "$artifacts/linux.config"
install -m 644 "$bout/.config" "$artifacts/busybox.config"
install -m 755 "$rootfs/bin/time64-probe" "$artifacts/time64-probe.armhf"
install -m 755 "$bout/busybox" "$artifacts/busybox.armhf"
cp "$project/config/sources.lock.json" "$artifacts/sources.lock.json"
cp "$project/patches/"*.patch "$artifacts/"
cp "$project/STATUS.md" "$artifacts/STATUS.md"
{
    "${cross}gcc" --version
    "${cross}ld" --version
    mkimage -V
    qemu-system-arm --version
} > "$artifacts/checks/toolchain.txt"
python3 "$project/tools/validate_artifacts.py" "$artifacts"
echo 'OFFLINE BUILD COMPLETE; NOT FLASHABLE/BOOT-VERIFIED. Read STATUS.md.'
