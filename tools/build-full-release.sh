#!/bin/bash
# Build all three offline firmware profiles from a checkout; never access hardware.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${TASKBASE:-"$project/.work"}
version=${VERSION:?Set VERSION for this offline build}
output=${OUTPUT:-"$project/build/release-$version"}
jobs=${JOBS:-4}
[[ "$version" =~ ^[0-9][A-Za-z0-9._-]{0,63}$ ]] || { echo 'Invalid VERSION' >&2; exit 1; }
test "$(id -u)" -ne 0 || { echo 'Build as a regular user' >&2; exit 1; }
test ! -e "$output" || { echo 'Use a new OUTPUT directory' >&2; exit 1; }
mkdir -p "$output"
output=$(cd -- "$output" && pwd)
export JOBS="$jobs" SOURCE_DATE_EPOCH=1791676800 TZ=UTC LC_ALL=C
cd -- "$project"
# RAM boot-gate tests use a PTY and pinned pyserial, without opening hardware.
python3 -m venv "$output/python"
"$output/python/bin/pip" install --require-hashes -r tools/requirements-serial.txt
export PATH="$output/python/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
make build TASKBASE="$taskbase"
make openwrt-toolchain TASKBASE="$taskbase"
make openwrt-router-emmcro TASKBASE="$taskbase"
make openwrt-container-applications TASKBASE="$taskbase"
commit=$(python3 -c 'import json; print(json.load(open("openwrt/sources.lock.json"))["openwrt"]["commit"])')
native_source="$taskbase/router-emmc/build/openwrt-ram-$commit"
combined_source="$taskbase/container-applications/build/openwrt-ram-$commit"
python3 tools/build_native_system.py --taskbase "$taskbase" --native-source "$native_source" \
    --persistent-candidate --work "$output/kernel"
python3 tools/package_native_system.py --taskbase "$taskbase" --kernel-build "$output/kernel" \
    --combined-source "$combined_source" --persistent-candidate \
    --work "$output/package-work" --output "$output/bootstrap"
python3 tools/prepare_native_disk_root.py --kernel-build "$output/kernel" \
    --package-work "$output/package-work" --skip-full-p9 --output "$output/disk"
make openwrt-release VERSION="$version" TASKBASE="$taskbase" NATIVE_SOURCE="$combined_source" \
    DISK_ROOT="$output/disk" BOOTSTRAP="$output/bootstrap" OUTPUT="$output/variants"
echo "Three-profile download assets: $output/variants/release/assets"
