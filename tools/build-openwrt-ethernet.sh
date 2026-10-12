#!/bin/bash
# Isolated native Ethernet RAM build; no physical board or installation access.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
stage=${2:-build}
jobs=${JOBS:-4}
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export SOURCE_DATE_EPOCH=1791676800
export TZ=UTC
export LC_ALL=C
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run the native Ethernet build as a regular user.' >&2
    exit 1
fi
case "$stage" in config|build) ;; *) echo 'Unknown Ethernet build stage' >&2; exit 1 ;; esac
source_tree=$(python3 "$project/tools/prepare_openwrt_ethernet.py" --taskbase "$taskbase")
make_args=(-C "$source_tree" "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" COMMITCOUNT=1)
make "${make_args[@]}" defconfig
python3 "$project/tools/check_openwrt_ethernet.py" --source "$source_tree"
if [ "$stage" = config ]; then
    exit 0
fi
make "${make_args[@]}" -j"$jobs" tools/install V=s
make "${make_args[@]}" -j"$jobs" toolchain/install V=s
make "${make_args[@]}" -j"$jobs" V=s
python3 "$project/tools/check_openwrt_ethernet.py" --source "$source_tree" --built
linuxsrc=$(find "$source_tree/build_dir" -path '*/linux-hi3798mv100_net/linux-6.12.112' -type d)
test -n "$linuxsrc"
python3 "$project/tools/test_femac_datapath.py" --linux "$linuxsrc"
python3 "$project/tools/test_openwrt_qemu.py" --source "$source_tree" --subtarget net
