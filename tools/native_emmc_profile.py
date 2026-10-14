"""Exact native low256 eMMC user-area read-only and guarded restart policy."""
import re

from emmc_ro_profile import NODE, OPTIONS, PROPERTIES, RESTART, RESTART_PROPERTIES

COMPATIBLE = "tianyi,ty1208z-ca-openwrt-emmcro-ram"
RELEASE = "-ty1208z-openwrt-emmcro"
VARIANT = "ethernet-emmcro"
PARTITIONS = ("blkdevparts=mmcblk0:1M(boot)ro,1M(bootargs)ro,4M(baseparam)ro,"
              "4M(pqparam)ro,4M(logo)ro,20M(kernel)ro,64M(busybox)ro,512M(backup)ro,6846M(ubuntu)ro")
BOOTARGS = ("console=ttyAMA0,115200 earlycon=pl011,mmio32,0xf8b00000 rdinit=/init "
            "loglevel=7 panic=0 " + PARTITIONS)
REQUIRED = OPTIONS | {"TY1208Z_ROUTER_EMMC_RO", "TY1208Z_ETHERNET_INHERITED"}
FORBIDDEN = {"TY1208Z_ROUTER_SD_RO", "TY1208Z_ROUTER_RAM768", "MMC_TEST", "MMC_DEBUG",
             "HI3798MV100_EMMC_READ_SAMPLES", "HI3798MV100_EMMC_AUDIT", "HI3798MV100_SD_AUDIT",
             "HI3798MV100_SD_READ_ONLY", "MMC_DW_HI3798MV100_SD_IDENT",
             "MTD", "ATA", "SCSI", "PCI", "USB_SUPPORT", "SMP", "HIGHMEM", "WATCHDOG", "PM",
             "DEBUG_FS", "BLK_DEV", "BLK_DEV_THROTTLING", "BLK_DEV_WRITE_MOUNTED", "FS_ENCRYPTION", "FS_VERITY"}


def native_emmc_configuration(config):
    active = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", config, re.MULTILINE))
    if any(active.get(name) != "y" for name in REQUIRED) or set(active) & FORBIDDEN:
        raise ValueError("Native eMMC lacks its built-in read-only configuration or enables other hardware")
    if (f'CONFIG_LOCALVERSION="{RELEASE}"\n' not in config or
            "CONFIG_MMC_BLOCK_MINORS=16\n" not in config):
        raise ValueError("Native eMMC release/partition count differs")
    storage = {name for name in active if name.startswith(("MMC", "PWRSEQ_", "BLK_DEV_", "POWER_RESET_"))}
    if storage - REQUIRED - {"BLK_DEV_INITRD", "POWER_RESET_HISI"}:
        raise ValueError("Unreviewed storage/reset driver in native eMMC")
    filesystems = {name for name in active if name.endswith("_FS")}
    if filesystems - {"PROC_FS", "OVERLAY_FS", "EXT4_FS"}:
        raise ValueError("Unreviewed filesystem in native eMMC")
    partitions = {name for name in active if name.endswith("_PARTITION")}
    if partitions - {"CMDLINE_PARTITION"}:
        raise ValueError("Unreviewed partition parser in native eMMC")


def native_emmc_profile(tree, config):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    identity = props.get("/", {}).get("compatible", {}).get("strings")
    if "CONFIG_TY1208Z_ROUTER_EMMC_RO=y\n" not in config:
        if identity == [COMPATIBLE, "hi3798mv100-series"]:
            raise ValueError("Native eMMC board lacks its explicit configuration")
        return False
    if (identity != [COMPATIBLE, "hi3798mv100-series"] or
            props.get("/memory@0", {}).get("reg", {}).get("cells") != [0, 0x10000000] or
            props.get("/chosen", {}).get("bootargs", {}).get("strings") != [BOOTARGS]):
        raise ValueError("Native eMMC identity/memory/partitions differ")
    native_emmc_configuration(config)
    for node, expected in ((NODE, PROPERTIES), (RESTART, RESTART_PROPERTIES)):
        if node not in props or set(props[node]) != set(expected):
            raise ValueError("Unreviewed native eMMC controller/reset property")
        for name, value in expected.items():
            for kind, content in value.items():
                if props[node][name].get(kind) != content:
                    raise ValueError("Native eMMC resource/clock/bus/reset differs")
    return True
