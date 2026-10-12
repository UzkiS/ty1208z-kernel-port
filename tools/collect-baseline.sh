#!/bin/sh
# Read-only baseline on the existing Hinas system. Send over SSH stdin.
# Output contains local hardware/log information: keep it in ignored evidence/.
# No installs, module loading, mounts, register access, writes or reboot.
export LC_ALL=C
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

section() { printf '\n--- %s ---\n' "$1"; }
show() {
    for source_path in "$@"; do
        if [ -r "$source_path" ]; then
            printf '\n[%s]\n' "$source_path"
            if ! cat "$source_path" 2>/dev/null; then
                printf '[read unavailable: %s]\n' "$source_path"
            fi
        fi
    done
}
optional() {
    if command -v "$1" >/dev/null 2>&1; then
        "$@" 2>&1 || printf '[command unavailable/failed: %s]\n' "$1"
    else
        printf '[command not installed: %s]\n' "$1"
    fi
}

printf 'TY1208Z_READONLY_BASELINE_BEGIN\n'
section 'Running system and CPU'
uname -a
id
date -u
show /etc/os-release /proc/version /proc/cmdline /proc/cpuinfo /proc/uptime
optional getconf LONG_BIT
optional getconf GNU_LIBC_VERSION
optional file /sbin/init

section 'Memory, reservations, interrupts and timing'
show /proc/meminfo /proc/iomem /proc/interrupts /proc/mtd /proc/mmz
show /sys/devices/system/cpu/online /sys/devices/system/cpu/possible
show /sys/devices/system/clocksource/clocksource0/current_clocksource
show /sys/devices/system/clocksource/clocksource0/available_clocksource
for cpu_clock in /sys/devices/system/cpu/cpu*/cpufreq; do
    [ -d "$cpu_clock" ] || continue
    show "$cpu_clock/scaling_cur_freq" "$cpu_clock/cpuinfo_max_freq"
done

section 'Current storage layout and mounted filesystems'
show /proc/partitions /proc/mounts
optional lsblk -b -o NAME,MAJ:MIN,SIZE,TYPE,FSTYPE,MOUNTPOINT
optional fdisk -l /dev/mmcblk0
for block_path in /sys/class/block/mmcblk*; do
    [ -d "$block_path" ] || continue
    show "$block_path/start" "$block_path/size" "$block_path/ro"
done
# Read identity facts without publishing the card's serial/CID.
for card_path in /sys/bus/mmc/devices/*; do
    [ -d "$card_path" ] || continue
    show "$card_path/type" "$card_path/name" "$card_path/manfid" "$card_path/oemid"
done

section 'USB topology and exact device/interface identities'
optional lsusb
optional lsusb -t
for usb_path in /sys/bus/usb/devices/*; do
    [ -d "$usb_path" ] || continue
    if [ -r "$usb_path/idVendor" ] || [ -r "$usb_path/bInterfaceClass" ]; then
        printf '\nUSB %s\n' "${usb_path##*/}"
        show "$usb_path/idVendor" "$usb_path/idProduct" "$usb_path/manufacturer"
        show "$usb_path/product" "$usb_path/bDeviceClass" "$usb_path/bDeviceSubClass"
        show "$usb_path/bInterfaceClass" "$usb_path/bInterfaceSubClass" "$usb_path/bInterfaceProtocol"
        show "$usb_path/modalias"
        [ ! -L "$usb_path/driver" ] || readlink "$usb_path/driver"
    fi
done

section 'SDIO identities'
for sdio_path in /sys/bus/sdio/devices/*; do
    [ -d "$sdio_path" ] || continue
    printf '\nSDIO %s\n' "${sdio_path##*/}"
    show "$sdio_path/vendor" "$sdio_path/device" "$sdio_path/class" "$sdio_path/modalias"
    [ ! -L "$sdio_path/driver" ] || readlink "$sdio_path/driver"
done

section 'Network interfaces and wireless capabilities'
optional ip -brief link
optional iw dev
optional iw phy
optional rfkill list
show /proc/net/wireless /proc/modules
for net_path in /sys/class/net/*; do
    [ -d "$net_path" ] || continue
    printf '\nInterface %s\n' "${net_path##*/}"
    [ ! -L "$net_path/device/driver" ] || readlink "$net_path/device/driver"
    show "$net_path/device/modalias" "$net_path/operstate"
    # Virtual interfaces expose these files but can reject reads with EINVAL.
    if [ -e "$net_path/device" ]; then
        show "$net_path/speed" "$net_path/duplex"
    fi
done

section 'Wireless modules available for the running kernel'
kernel_release=$(uname -r)
module_root="/lib/modules/$kernel_release"
if [ -d "$module_root" ]; then
    show "$module_root/modules.builtin" | grep -Ei 'wifi|wlan|rtl|cfg80211|mac80211|usb|mmc' || :
    find "$module_root" -type f \( -iname '*8188*.ko*' -o -iname '*rda*.ko*' \
        -o -iname '*cfg80211*.ko*' -o -iname '*mac80211*.ko*' \) \
        -exec sh -c '
            for module_path do
                printf "\nModule file: %s\n" "$module_path"
                if command -v modinfo >/dev/null 2>&1; then
                    modinfo "$module_path" 2>&1 | grep -E "^(filename|version|firmware|alias|depends|vermagic):"
                fi
            done
        ' sh {} + 2>&1
fi

section 'Relevant running kernel configuration'
config_filter='^(CONFIG_|# CONFIG_)(ARCH_|CPU_|SMP|NR_CPUS|PHYS_OFFSET|PAGE_OFFSET|ARM_APPENDED_DTB|ARM_ATAG_DTB_COMPAT|CMDLINE|IKCONFIG|HIGHMEM|CMA|HISI|HI3|HIMCI|HIETH|MMC|USB|CFG80211|MAC80211|WLAN|WIRELESS|RTL|R8|RDA|FW_LOADER|SERIAL_AMBA|ARM_GIC|ARM_TIMER|HISP804|KEXEC|COMPAT_32BIT_TIME)'
if [ -r /proc/config.gz ]; then
    gzip -dc /proc/config.gz | grep -E "$config_filter" || :
elif [ -r "/boot/config-$kernel_release" ]; then
    grep -E "$config_filter" "/boot/config-$kernel_release" || :
else
    printf '[running kernel config not exposed]\n'
fi

section 'Device tree identity and chosen arguments'
dt_root=/sys/firmware/devicetree/base
for dt_path in model compatible chosen/bootargs chosen/stdout-path; do
    if [ -r "$dt_root/$dt_path" ]; then
        printf '\nDT %s\n' "$dt_path"
        tr '\000' '\n' < "$dt_root/$dt_path"
        printf '\n'
    fi
done
if [ -r /sys/firmware/fdt ] && command -v base64 >/dev/null 2>&1; then
    # Keep the actual DTB locally inside this text report, without disk writes
    # on the remote box. Decode/review it before drawing memory conclusions.
    printf 'RUNNING_FDT_BASE64_BEGIN\n'
    base64 /sys/firmware/fdt
    printf 'RUNNING_FDT_BASE64_END\n'
fi

section 'Current kernel boot/device messages'
optional dmesg
printf '\nTY1208Z_READONLY_BASELINE_END\n'
# Windows PowerShell can append CRLF to an LF script on native-process stdin.
# Stop here so the trailing CR is never interpreted as another shell command.
exit 0
