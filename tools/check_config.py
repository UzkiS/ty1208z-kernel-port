#!/usr/bin/env python3
"""Fail on omitted essential options or enabled persistent-storage drivers."""
from pathlib import Path
import sys

def load(path):
    return dict(line.split("=", 1) for line in Path(path).read_text().splitlines()
                if line.startswith("CONFIG_") and "=" in line)

linux, busybox = map(load, sys.argv[1:3])
effective = load(sys.argv[3]) if len(sys.argv) > 3 else linux
for name in ("MMU", "ARCH_MULTI_V7", "ARCH_HISI", "ARCH_HI3798MV100", "HI3798MV100_TIMER",
             "ARCH_VIRT", "ARM_GIC", "COMMON_CLK", "OF", "ARM_APPENDED_DTB",
             "AEABI", "VFP", "SERIAL_AMBA_PL011", "SERIAL_AMBA_PL011_CONSOLE",
             "SERIAL_EARLYCON", "BLK_DEV_INITRD", "DEVTMPFS", "TMPFS", "PROC_FS",
             "SYSFS", "BINFMT_ELF", "BINFMT_SCRIPT", "IKCONFIG_PROC", "PRINTK",
             "ARM_PATCH_PHYS_VIRT", "AUTO_ZRELADDR", "POSIX_TIMERS", "COMPAT_32BIT_TIME"):
    assert linux.get("CONFIG_" + name) == "y", f"Required Linux option missing: {name}"
    assert effective.get("CONFIG_" + name) == "y", f"Compiled kernel config stale/missing: {name}"
for name in ("SMP", "MODULES", "BLOCK", "NET", "MMC", "USB_SUPPORT", "MTD", "ATA",
             "SCSI", "PM", "SUSPEND", "ARM_ATAG_DTB_COMPAT"):
    assert linux.get("CONFIG_" + name, "n") == "n", f"Unexpected Linux option: {name}"
    assert effective.get("CONFIG_" + name, "n") == "n", f"Unexpected compiled Linux option: {name}"
for name in ("STATIC", "BUSYBOX", "LFS", "TIME64", "FEATURE_INSTALLER", "ASH", "MOUNT", "CTTYHACK", "SETSID",
             "DATE", "STAT", "FEATURE_STAT_FORMAT", "FEATURE_TEST_64", "TOUCH", "GREP", "POWEROFF"):
    assert busybox.get("CONFIG_" + name) == "y", f"Required BusyBox option missing: {name}"
assert linux.get("CONFIG_INITRAMFS_SOURCE", '""') != '""'
print("Config verification passed: single core, RAM initramfs, no disk/network drivers, time64 BusyBox")
