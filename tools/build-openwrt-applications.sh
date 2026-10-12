#!/bin/bash
# Isolated native applications; no physical board access or installation.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
stage=${2:-build}
jobs=${JOBS:-4}
export GOMAXPROCS=${GOMAXPROCS:-$jobs}
# WSL imports Windows PATH entries containing spaces/colons; OpenWrt's final
# find -execdir gate correctly rejects the resulting relative components.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run the application build as a regular user.' >&2
    exit 1
fi
case "$stage" in config|build) ;; *) echo 'Unknown application stage' >&2; exit 1 ;; esac
export SOURCE_DATE_EPOCH=1791676800
export TZ=UTC
export LC_ALL=C
source_tree=$(python3 "$project/tools/prepare_openwrt_applications.py" --taskbase "$taskbase")
make_args=(-C "$source_tree" "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" COMMITCOUNT=1)
(
    cd "$source_tree"
    ./scripts/feeds update -a
    # Install only the application roots and their dependency recipes. Installing
    # every unrelated LuCI app introduces upstream Kconfig dependency cycles.
    ./scripts/feeds uninstall -a
    ./scripts/feeds install -f -p passwall_packages xray-core
    ./scripts/feeds install -p luci luci luci-ssl
    ./scripts/feeds install -f -p passwall luci-app-passwall luci-i18n-passwall-zh-cn
    ./scripts/feeds install -p packages curl
)
# Feed indexing can resolve .config before all package recipes exist. Apply the
# authoritative selection only after the complete dependency set is installed.
cp "$source_tree/.ty1208z-application.config" "$source_tree/.config"
make "${make_args[@]}" defconfig
python3 "$project/tools/check_openwrt_applications.py" --source "$source_tree"
if [ "$stage" = config ]; then
    exit 0
fi
make "${make_args[@]}" -j"$jobs" tools/install V=s
make "${make_args[@]}" -j"$jobs" toolchain/install V=s
make "${make_args[@]}" -j"$jobs" V=s
python3 "$project/tools/check_openwrt_applications.py" --source "$source_tree" --built
python3 "$project/tools/test_openwrt_applications_qemu.py" --source "$source_tree"
