#!/bin/bash
# Compile/package in a separate native tree; no exported boot image or board access.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
jobs=${JOBS:-4}
python_cmd=$(command -v python3)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export SOURCE_DATE_EPOCH=1791676800
export TZ=UTC LC_ALL=C
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run the native package build as a regular user.' >&2
    exit 1
fi
source_tree=$("$python_cmd" "$project/tools/prepare_openwrt_wifi.py" --taskbase "$taskbase")
make_args=(-C "$source_tree" "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" COMMITCOUNT=1)
make "${make_args[@]}" defconfig
"$python_cmd" "$project/tools/check_openwrt_wifi.py" --source "$source_tree"
make "${make_args[@]}" -j"$jobs" tools/install V=s
make "${make_args[@]}" -j"$jobs" toolchain/install V=s
make "${make_args[@]}" -j"$jobs" target/linux/compile V=s
make "${make_args[@]}" -j"$jobs" package/kernel/ty1208z-rda-port/compile V=s
# Exercise the parser from the actual native package source, not just the
# standalone port: native preparation can otherwise leave a stale source.
native_kernels=("$source_tree"/build_dir/target-*/linux-hi3798mv100_ram/linux-6.12.112)
native_packages=("$source_tree"/build_dir/target-*/linux-hi3798mv100_ram/ty1208z-rda-port-*)
if [ "${#native_kernels[@]}" -ne 1 ] || [ ! -d "${native_kernels[0]}" ] ||
   [ "${#native_packages[@]}" -ne 1 ] || [ ! -d "${native_packages[0]}/rdawlan" ]; then
    echo 'Expected one actual native Linux tree and RDA package source.' >&2
    exit 1
fi
"$python_cmd" "$project/tools/test_wifi_assoc_frames.py" \
    --source "${native_packages[0]}" --linux "${native_kernels[0]}"
"$python_cmd" "$project/tools/check_openwrt_wifi.py" --source "$source_tree" --built
"$python_cmd" "$project/tools/test_openwrt_wifi_package.py" --source "$source_tree"
# Include the actual-APK rejection report in the exported hash manifest.
"$python_cmd" "$project/tools/check_openwrt_wifi.py" --source "$source_tree" --built
