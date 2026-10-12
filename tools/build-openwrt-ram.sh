#!/bin/bash
# Native, offline-only OpenWrt build; no serial access or installation actions.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
stage=${2:-build}
jobs=${JOBS:-16}
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run the native OpenWrt build as a regular user.' >&2
    exit 1
fi
case "$stage" in config|toolchain|build) ;; *) echo 'Unknown build stage' >&2; exit 1 ;; esac
export SOURCE_DATE_EPOCH=1791676800
export TZ=UTC
export LC_ALL=C
source_tree=$(python3 "$project/tools/prepare_openwrt.py" --taskbase "$taskbase")
# Archive builds use a fixed local package revision, not the timestamp-based
# commit-count fallback or a fabricated upstream Git history.
make_args=(-C "$source_tree" "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" COMMITCOUNT=1)
make "${make_args[@]}" defconfig
python3 "$project/tools/check_openwrt.py" --source "$source_tree"
if [ "$stage" = config ]; then
    exit 0
fi
make "${make_args[@]}" -j"$jobs" tools/install V=s
make "${make_args[@]}" -j"$jobs" toolchain/install V=s
if [ "$stage" = toolchain ]; then
    exit 0
fi
make "${make_args[@]}" -j"$jobs" V=s
python3 "$project/tools/check_openwrt.py" --source "$source_tree" --built
python3 "$project/tools/test_openwrt_qemu.py" --source "$source_tree"
