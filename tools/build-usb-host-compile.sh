#!/bin/bash
# No image/DTB: compile optional shared host0 provider and generic companion HCDs.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=$(realpath -m -- "${1:-"$project/.work"}")
linuxsrc="$taskbase/src/linux-6.12.112"
diagnostic="$taskbase/build/linux-diagnostic"
kout="$taskbase/build/linux-usb-host-compile"
cross=${CROSS_COMPILE:-arm-linux-gnueabihf-}
test -f "$diagnostic/.config" || { echo 'Run make build first.' >&2; exit 1; }
for name in clk-ty1208z-usb.c ty1208z-usb-host0.h; do
    cmp "$project/overlay/drivers/clk/hisilicon/$name" "$linuxsrc/drivers/clk/hisilicon/$name"
done
python3 "$project/tools/fetch_references.py"
python3 "$project/tools/test_usb_host0.py"
mkdir -p "$kout"
cp "$diagnostic/.config" "$kout/.config"
python3 "$project/tools/merge_fragment.py" "$kout/.config" "$project/config/linux-usb-host-compile.fragment"
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" olddefconfig syncconfig
for option in TY1208Z_USB_HOST0_EXPERIMENT USB USB_EHCI_HCD_PLATFORM USB_OHCI_HCD_PLATFORM; do
    grep -qx "CONFIG_${option}=y" "$kout/.config"
done
for option in BLOCK MMC MTD NET MODULES PM SMP DEBUG_FS USB_STORAGE USB_UAS; do
    if grep -qE "^CONFIG_${option}=[ym]$" "$kout/.config"; then
        echo "Unexpected subsystem: $option" >&2
        exit 1
    fi
done
make -C "$linuxsrc" O="$kout" ARCH=arm CROSS_COMPILE="$cross" -j"${JOBS:-16}" \
    drivers/clk/hisilicon/clk-ty1208z-usb.o \
    drivers/usb/host/ehci-hcd.o drivers/usb/host/ehci-platform.o \
    drivers/usb/host/ohci-hcd.o drivers/usb/host/ohci-platform.o
"${cross}readelf" -h "$kout/drivers/clk/hisilicon/clk-ty1208z-usb.o"
python3 - "$project" "$kout" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

project, build = map(Path, sys.argv[1:])
names = (
    "drivers/clk/hisilicon/clk-ty1208z-usb.o",
    "drivers/usb/host/ehci-hcd.o", "drivers/usb/host/ehci-platform.o",
    "drivers/usb/host/ohci-hcd.o", "drivers/usb/host/ohci-platform.o",
)
result = {
    "status": "compile and sanitized SDK differential checks only; no boot image or hardware acceptance",
    "objects": {name: {"bytes": (build / name).stat().st_size,
                       "sha256": hashlib.sha256((build / name).read_bytes()).hexdigest()}
                for name in names},
}
output = project / "artifacts/usb-host-compile"
output.mkdir(parents=True, exist_ok=True)
(output / "checks.json").write_text(json.dumps(result, indent=2) + "\n")
(output / "linux.config").write_bytes((build / ".config").read_bytes())
PY
echo 'USB HOST0 COMPILE ONLY; no DTB/boot image, USB device transactions or firmware.'
