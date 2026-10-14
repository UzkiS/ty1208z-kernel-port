#!/bin/bash
# Independent native composition for QEMU; no board boot/package/install path.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
stage=${2:-build}
jobs=${JOBS:-4}
export GOMAXPROCS=${GOMAXPROCS:-$jobs}
python_cmd=$(command -v python3)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if [ "$(id -u)" -eq 0 ]; then echo 'Run native builds as a regular user.' >&2; exit 1; fi
case "$stage" in config|build) ;; *) echo 'Unknown combined container application stage' >&2; exit 1 ;; esac
if [ "$stage" = build ]; then
    rm -f "$project/artifacts/openwrt-container-applications-qemu/manifest.json"
fi
export SOURCE_DATE_EPOCH=1791676800 TZ=UTC LC_ALL=C
source_tree=$("$python_cmd" "$project/tools/prepare_openwrt_applications.py" --taskbase "$taskbase" --container-applications)
make_args=(-C "$source_tree" "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" COMMITCOUNT=1)
(
    cd "$source_tree"
    ./scripts/feeds update -a
    ./scripts/feeds uninstall -a
    ./scripts/feeds install -f -p passwall_packages xray-core sing-box
    ./scripts/feeds install -p luci luci luci-ssl luci-i18n-base-zh-cn luci-i18n-firewall-zh-cn
    ./scripts/feeds install -f -p passwall luci-app-passwall luci-i18n-passwall-zh-cn
    ./scripts/feeds install -p packages curl unzip docker dockerd containerd runc tini iperf3
)
cp "$source_tree/.ty1208z-application.config" "$source_tree/.config"
make "${make_args[@]}" defconfig
"$python_cmd" "$project/tools/check_openwrt_applications.py" --source "$source_tree"
"$python_cmd" "$project/tools/check_openwrt_containers.py" --source "$source_tree" --application-runtime
if [ "$stage" = config ]; then exit 0; fi
make "${make_args[@]}" -j"$jobs" tools/install V=s
make "${make_args[@]}" -j"$jobs" toolchain/install V=s
make "${make_args[@]}" -j"$jobs" V=s
"$python_cmd" "$project/tools/check_openwrt_applications.py" --source "$source_tree" --built
"$python_cmd" "$project/tools/check_openwrt_containers.py" --source "$source_tree" --built --application-runtime
"$python_cmd" "$project/tools/test_openwrt_applications_qemu.py" --source "$source_tree" --memory-mib 768 --taskbase "$taskbase"
"$python_cmd" "$project/tools/export_openwrt_container_applications.py" --source "$source_tree"
echo OPENWRT_CONTAINER_APPLICATIONS_QEMU_ONLY_PASS
