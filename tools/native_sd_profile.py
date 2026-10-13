"""Exact native read-only SD configuration/resources; no ordinary profile relaxation."""
import re

from sd_ident_profile import NODE, PROPERTIES

COMPATIBLE = "tianyi,ty1208z-ca-openwrt-sdro-ram"
RELEASE = "-ty1208z-openwrt-sdro"
VARIANT = "ethernet-sdro"
REQUIRED = {"TY1208Z_ROUTER_SD_RO", "BLOCK", "MMC", "MMC_BLOCK", "MMC_DW", "MMC_DW_PLTFM",
            "MMC_DW_HI3798MV100_SD_IDENT", "HI3798MV100_SD_READ_ONLY", "EXT4_FS",
            "FAT_FS", "VFAT_FS", "EXFAT_FS", "NLS_UTF8", "PARTITION_ADVANCED",
            "MSDOS_PARTITION", "EFI_PARTITION", "PROC_PAGE_MONITOR"}
FORBIDDEN = {"TY1208Z_ROUTER_RAM768", "MMC_DW_HI3798MV100_IDENT", "MMC_TEST", "MMC_DEBUG",
             "HI3798MV100_EMMC_READ_SAMPLES", "HI3798MV100_EMMC_AUDIT", "HI3798MV100_SD_AUDIT",
             "MTD", "ATA", "SCSI", "PCI", "USB_SUPPORT", "SMP", "HIGHMEM", "WATCHDOG", "PM",
             "DEBUG_FS", "BLK_DEV", "BLK_DEV_THROTTLING", "BLK_DEV_WRITE_MOUNTED", "FS_ENCRYPTION", "FS_VERITY",
             "POWER_RESET_TY1208Z_MV100_SD", "POWER_RESET_TY1208Z_MV100_RAM",
             "POWER_RESET_TY1208Z_SP805"}


def native_sd_configuration(config):
    active = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", config, re.MULTILINE))
    if any(active.get(name) != "y" for name in REQUIRED) or set(active) & FORBIDDEN:
        raise ValueError("Native SD lacks its built-in read-only configuration or enables other hardware")
    if (f'CONFIG_LOCALVERSION="{RELEASE}"\n' not in config or
            "CONFIG_MMC_BLOCK_MINORS=16\n" not in config):
        raise ValueError("Native SD release/partition count differs")
    storage = {name for name in active if name.startswith(("MMC", "PWRSEQ_", "BLK_DEV_", "POWER_RESET_"))}
    unexpected_storage = storage - REQUIRED - {"BLK_DEV_INITRD", "POWER_RESET_HISI"}
    if unexpected_storage:
        raise ValueError("Unreviewed storage/reset driver in native SD: " + ", ".join(sorted(unexpected_storage)))
    filesystems = {name for name in active if name.endswith("_FS")}
    # OpenWrt's inherited overlay operates on the RAM root; it is not another
    # card filesystem or a way around the request-level write filter.
    unexpected_filesystems = filesystems - {"PROC_FS", "OVERLAY_FS", "EXT4_FS", "FAT_FS", "VFAT_FS", "EXFAT_FS"}
    if unexpected_filesystems:
        raise ValueError("Unreviewed filesystem in native SD: " + ", ".join(sorted(unexpected_filesystems)))


def native_sd_profile(tree, config):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    identity = props.get("/", {}).get("compatible", {}).get("strings")
    if "CONFIG_TY1208Z_ROUTER_SD_RO=y\n" not in config:
        if identity == [COMPATIBLE, "hi3798mv100-series"]:
            raise ValueError("Native SD board lacks its explicit configuration")
        return False
    if (identity != [COMPATIBLE, "hi3798mv100-series"] or
            props.get("/memory@0", {}).get("reg", {}).get("cells") != [0, 0x30000000]):
        raise ValueError("Native SD identity/memory bound differs")
    native_sd_configuration(config)
    if NODE not in props or set(props[NODE]) != set(PROPERTIES):
        raise ValueError("Unreviewed native SD controller/property")
    for name, value in PROPERTIES.items():
        for kind, expected in value.items():
            if props[NODE][name].get(kind) != expected:
                raise ValueError("Native SD resource/clock/bus differs")
    return True
