#!/bin/bash
# Compile one USB translation unit, without linking/loading a driver or firmware.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
taskbase=$(realpath -m -- "$taskbase")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-wifi-usb-audit"
pristine="$taskbase/rda-usb/source"
port="$taskbase/rda-usb/usb-audit"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
if [ ! -f "$diagnostic/.config" ] || [ ! -f "$linuxsrc/Makefile" ]; then
    echo 'Run make build first; audit requires the pinned diagnostic source/config.' >&2
    exit 1
fi
mkdir -p "$kout" "$port"
python3 "$project/tools/fetch_wifi.py" --output "$pristine"
python3 "$project/tools/make_wifi_usb_patch.py" --source "$pristine" \
    --output "$project/patches/0003-rda-usb-api-audit.patch"
cp -a "$pristine/." "$port/"
patch --forward --batch -d "$port" -p1 < "$project/patches/0003-rda-usb-api-audit.patch"
# Override the vendor's SDIO-default build; only the USB translation unit is
# compiled. This is deliberately not a complete rdawfmac module.
cat > "$port/rdawlan/Kbuild" <<'KBUILD'
obj-m += rdawfmac.o
rdawfmac-y := wland_usb.o
ccflags-y += -I$(src)/../include -DCONFIG_RDAWFMAC_USB -DWLAND_LINUX_SUPPORT
KBUILD
cp "$diagnostic/.config" "$kout/.config"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-wifi-usb-audit.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig modules_prepare
for option in NET WIRELESS CFG80211 USB MODULES; do
    if ! grep -qx "CONFIG_${option}=y" "$kout/.config"; then
        echo "Required audit option missing: CONFIG_${option}" >&2
        exit 1
    fi
done
make -C "$linuxsrc" O="$kout" M="$port/rdawlan" ARCH=arm CROSS_COMPILE="$cross" wland_usb.o
"${cross}readelf" -h "$port/rdawlan/wland_usb.o"
echo 'USB OBJECT COMPILE ONLY; no full module, firmware, hardware or network validation.'
