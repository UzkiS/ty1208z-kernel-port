#!/bin/bash
# Native package compilation only; no RAM boot, rootfs or device access.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
stage=${2:-build}
jobs=${JOBS:-4}
export GOMAXPROCS=${GOMAXPROCS:-$jobs}
python_cmd=$(command -v python3)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if [ "$(id -u)" -eq 0 ]; then echo 'Run native builds as a regular user.' >&2; exit 1; fi
case "$stage" in config|build) ;; *) echo 'Unknown container package stage' >&2; exit 1 ;; esac
export SOURCE_DATE_EPOCH=1791676800 TZ=UTC LC_ALL=C
source_tree=$("$python_cmd" "$project/tools/prepare_openwrt_applications.py" --taskbase "$taskbase" --container-packages)
make_args=(-C "$source_tree" "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" COMMITCOUNT=1)
(
    cd "$source_tree"
    ./scripts/feeds update -a
    ./scripts/feeds uninstall -a
    ./scripts/feeds install -p packages docker dockerd containerd runc tini
)
cp "$source_tree/.ty1208z-application.config" "$source_tree/.config"
make "${make_args[@]}" defconfig
"$python_cmd" "$project/tools/check_openwrt_containers.py" --source "$source_tree"
if [ "$stage" = config ]; then exit 0; fi
make "${make_args[@]}" -j"$jobs" tools/install V=s
make "${make_args[@]}" -j"$jobs" toolchain/install V=s
# Do not invoke image/install or build an application RAM candidate.
make "${make_args[@]}" -j"$jobs" target/linux/compile V=s
make "${make_args[@]}" -j"$jobs" package/compile V=s
"$python_cmd" "$project/tools/check_openwrt_containers.py" --source "$source_tree" --built
