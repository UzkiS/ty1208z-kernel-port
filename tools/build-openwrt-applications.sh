#!/bin/bash
# Isolated native applications; no physical board access or installation.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
stage=${2:-build}
jobs=${JOBS:-4}
export GOMAXPROCS=${GOMAXPROCS:-$jobs}
# Preserve the caller's Python/serial environment across the restricted PATH.
python_cmd=$(command -v python3)
# WSL imports Windows PATH entries containing spaces/colons; OpenWrt's final
# find -execdir gate correctly rejects the resulting relative components.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run the application build as a regular user.' >&2
    exit 1
fi
case "$stage" in config|build|ram|network-config|network|network-ram768|network-sdro|network-emmcro) ;; *) echo 'Unknown application stage' >&2; exit 1 ;; esac
export SOURCE_DATE_EPOCH=1791676800
export TZ=UTC
export LC_ALL=C
prepare_args=(--taskbase "$taskbase")
if [[ "$stage" == network* ]]; then prepare_args+=(--ethernet); fi
if [ "$stage" = network-ram768 ]; then prepare_args+=(--ram768); fi
if [ "$stage" = network-sdro ]; then prepare_args+=(--sd-read-only); fi
if [ "$stage" = network-emmcro ]; then prepare_args+=(--emmc-read-only); fi
source_tree=$("$python_cmd" "$project/tools/prepare_openwrt_applications.py" "${prepare_args[@]}")
make_args=(-C "$source_tree" "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" COMMITCOUNT=1)
(
    cd "$source_tree"
    ./scripts/feeds update -a
    # Install only the application roots and their dependency recipes. Installing
    # every unrelated LuCI app introduces upstream Kconfig dependency cycles.
    ./scripts/feeds uninstall -a
    ./scripts/feeds install -f -p passwall_packages xray-core sing-box
    ./scripts/feeds install -p luci luci luci-ssl luci-i18n-base-zh-cn luci-i18n-firewall-zh-cn
    ./scripts/feeds install -f -p passwall luci-app-passwall luci-i18n-passwall-zh-cn
    ./scripts/feeds install -p packages curl unzip
    if [[ "$stage" == network* ]]; then ./scripts/feeds install -p packages iperf3; fi
)
# Feed indexing can resolve .config before all package recipes exist. Apply the
# authoritative selection only after the complete dependency set is installed.
cp "$source_tree/.ty1208z-application.config" "$source_tree/.config"
make "${make_args[@]}" defconfig
"$python_cmd" "$project/tools/check_openwrt_applications.py" --source "$source_tree"
if [ "$stage" = config ] || [ "$stage" = network-config ]; then
    exit 0
fi
make "${make_args[@]}" -j"$jobs" tools/install V=s
make "${make_args[@]}" -j"$jobs" toolchain/install V=s
make "${make_args[@]}" -j"$jobs" V=s
"$python_cmd" "$project/tools/check_openwrt_applications.py" --source "$source_tree" --built
xray_source=$(find "$source_tree/build_dir" -maxdepth 2 -type d -name 'Xray-core-26.10.10')
test -n "$xray_source"
"$python_cmd" "$project/tools/test_xray_browser_clock.py" --source "$xray_source" \
    --go "$source_tree/staging_dir/hostpkg/lib/go-1.27/bin/go" \
    --archive "$source_tree/dl/Xray-core-26.10.10.tar.gz"
"$python_cmd" "$project/tools/test_openwrt_applications_qemu.py" --source "$source_tree"
if [ "$stage" = ram ] || [[ "$stage" == network* ]]; then
    "$python_cmd" "$project/tools/test_openwrt_applications_qemu.py" --source "$source_tree" --memory-mib 256
    "$python_cmd" "$project/tools/make_openwrt_apps_ram.py" --source "$source_tree"
    if [[ "$stage" == network* ]]; then
        ram_artifacts="$project/artifacts/openwrt-router1"
        if [ "$stage" = network-ram768 ]; then ram_artifacts="$project/artifacts/openwrt-router768"; fi
        if [ "$stage" = network-sdro ]; then ram_artifacts="$project/artifacts/openwrt-router-sdro"; fi
        if [ "$stage" = network-emmcro ]; then ram_artifacts="$project/artifacts/openwrt-router-emmcro"; fi
        "$python_cmd" "$project/tools/test_openwrt_apps_ram.py" --artifacts "$ram_artifacts"
        "$python_cmd" "$project/tools/test_ethernet_net.py"
    else
        "$python_cmd" "$project/tools/test_openwrt_apps_ram.py"
    fi
fi
