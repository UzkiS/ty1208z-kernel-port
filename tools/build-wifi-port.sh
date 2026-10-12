#!/bin/bash
# Compile/link only, never load a driver, access hardware or fetch firmware.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-wifi-port"
pristine="$taskbase/rda-usb/source"
port="$taskbase/rda-usb/linux-6.12-port"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
export SOURCE_DATE_EPOCH=1791676800
export KBUILD_BUILD_TIMESTAMP='2026-10-11 00:00:00 UTC'
export KBUILD_BUILD_USER=ty1208z
export KBUILD_BUILD_HOST=offline
export KBUILD_BUILD_VERSION=1
if [ ! -f "$diagnostic/.config" ]; then
    echo 'Run make build first; Wi-Fi port uses the pinned kernel source.' >&2
    exit 1
fi
mkdir -p "$kout" "$port" "$project/artifacts/wifi-port/checks"
python3 "$project/tools/fetch_wifi.py" --output "$pristine"
python3 "$project/tools/make_wifi_usb_patch.py" --source "$pristine" \
    --output "$project/patches/0003-rda-usb-api-audit.patch"
python3 "$project/tools/make_wifi_port_patch.py" --source "$pristine" \
    --output "$project/patches/0004-rda-linux-6.12-port.patch"
cp -a "$pristine/." "$port/"
# This project-owned generated header is absent from the pristine vendor tree.
rm -f -- "$port/rdawlan/wland_port_key.h"
rm -f -- "$port/rdawlan/wland_port_key_validate.h"
patch --forward --batch -d "$port" -p1 < "$project/patches/0003-rda-usb-api-audit.patch"
patch --forward --batch -d "$port" -p1 < "$project/patches/0004-rda-linux-6.12-port.patch"
python3 "$project/tools/test_wifi_port.py" --source "$port"
python3 "$project/tools/test_wifi_control.py" --source "$port"
python3 "$project/tools/test_wifi_keys.py" --source "$port" --linux "$linuxsrc"
python3 "$project/tools/test_wifi_operations.py" --source "$port" --linux "$linuxsrc"
python3 "$project/tools/test_wifi_startup.py" --source "$port"
cat > "$port/rdawlan/Kbuild" <<'KBUILD'
obj-m += rdawfmac.o
rdawfmac-y := wland_p2p.o wland_dbg.o wland_d11.o wland_nvram.o wland_utils.o \
    wland_trap.o wland_bus.o wland_cmds.o wland_fwsmgr.o wland_wid.o wland_fweh.o \
    wland_linux.o wland_cfg80211.o wland_android.o wland_rx.o wland_rf.o \
    wland_amsdu.o wland_usb.o
ccflags-y += -I$(src)/../include -DCONFIG_RDAWFMAC_USB -DWLAND_LINUX_SUPPORT
KBUILD
cp "$diagnostic/.config" "$kout/.config"
cp "$diagnostic/initramfs.cpio" "$kout/initramfs.cpio"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-wifi-port.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" -j"${JOBS:-16}" vmlinux modules
make -C "$linuxsrc" O="$kout" M="$port/rdawlan" ARCH=arm CROSS_COMPILE="$cross" -j"${JOBS:-16}" modules
"${cross}readelf" -h "$port/rdawlan/rdawfmac.ko" > "$project/artifacts/wifi-port/checks/elf.txt"
"${cross}nm" "$port/rdawlan/rdawfmac.ko" > "$project/artifacts/wifi-port/checks/symbols.txt"
if grep -Eq 'wland_(efuse_set_|write_efuse_|write_txpower_to_efuse|rf_test_cmd)' \
    "$project/artifacts/wifi-port/checks/symbols.txt"; then
    echo 'Manufacturing eFuse write symbol survives; refuse this module.' >&2
    exit 1
fi
cp "$port/rdawlan/rdawfmac.ko" "$project/artifacts/wifi-port/rdawfmac-UNTESTED.ko"
cp "$kout/.config" "$project/artifacts/wifi-port/linux.config"
cp "$project/config/sources.lock.json" "$project/reference/wifi-rda-usb.lock.json" \
    "$project/patches/0003-rda-usb-api-audit.patch" "$project/patches/0004-rda-linux-6.12-port.patch" \
    "$project/artifacts/wifi-port/"
python3 "$project/tools/validate_wifi_port.py" "$project/artifacts/wifi-port"
echo 'FULL MODULE LINKED; hardware, firmware initialization, scan/STA/AP untested.'
