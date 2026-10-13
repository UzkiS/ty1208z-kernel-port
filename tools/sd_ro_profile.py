"""Exact SD read-only block/filesystem RAM profile, separate from metadata-only."""
import re

from sd_ident_profile import BASE_PATHS, NODE, RESTART, PROPERTIES, RESTART_PROPERTIES

CONFIG = 'CONFIG_LOCALVERSION="-ty1208z-sd-ro1"\n'
OPTIONS = {"MMC", "MMC_DW", "MMC_DW_PLTFM", "MMC_DW_HI3798MV100_SD_IDENT",
           "HI3798MV100_SD_READ_ONLY", "BLOCK", "MMC_BLOCK", "POWER_RESET",
           "POWER_RESET_TY1208Z_MV100_SD", "EXT4_FS", "FAT_FS", "VFAT_FS", "EXFAT_FS",
           "PARTITION_ADVANCED", "MSDOS_PARTITION", "EFI_PARTITION", "NLS_UTF8"}


def sd_ro_profile(tree, config):
    if "CONFIG_TY1208Z_ROUTER_SD_RO=y\n" in config:
        from ethernet_net_profile import openwrt_router_sdro_ethernet_profile
        return openwrt_router_sdro_ethernet_profile(tree, config)
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    enabled = "CONFIG_HI3798MV100_SD_READ_ONLY=y\n" in config
    identity = props.get("/", {}).get("compatible", {}).get("strings", [])
    if not enabled:
        if "tianyi,ty1208z-ca-sd-ro-ram" in identity:
            raise ValueError("SD read-only board without its explicit policy")
        return False
    if CONFIG not in config or set(props) != BASE_PATHS | {NODE, RESTART}:
        raise ValueError("Unexpected SD read-only release/peripheral")
    if identity != ["tianyi,ty1208z-ca-sd-ro-ram", "hi3798mv100-series"]:
        raise ValueError("Unexpected SD read-only board identity")
    for node, expected in ((NODE, PROPERTIES), (RESTART, RESTART_PROPERTIES)):
        if set(props[node]) != set(expected):
            raise ValueError("Unreviewed SD read-only controller/restart property")
        for name, value in expected.items():
            for kind, content in value.items():
                if props[node][name].get(kind) != content:
                    raise ValueError("SD read-only resource/clock/bus differs")
    active = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", config, re.MULTILINE))
    if any(active.get(name) != "y" for name in OPTIONS):
        raise ValueError("Incomplete SD read-only block/filesystem configuration")
    if "CONFIG_MMC_BLOCK_MINORS=16\n" not in config:
        raise ValueError("SD read-only partition minor count differs")
    restricted = {name for name in active if name.startswith(("MMC", "POWER_RESET_", "PWRSEQ_", "BLK_DEV_"))}
    if restricted - OPTIONS - {"POWER_RESET_HISI", "BLK_DEV_INITRD"}:
        raise ValueError("Unreviewed storage/reset driver in SD read-only profile")
    filesystems = {name for name in active if name.endswith("_FS")}
    if filesystems - {"PROC_FS", "EXT4_FS", "FAT_FS", "VFAT_FS", "EXFAT_FS"}:
        raise ValueError("Unreviewed filesystem in SD read-only profile")
    forbidden = {"NET", "MODULES", "SMP", "USB_SUPPORT", "MTD", "ATA", "SCSI", "PCI",
                 "WATCHDOG", "DEBUG_FS", "PM", "HI3798MV100_SD_AUDIT", "HI3798MV100_EMMC_AUDIT",
                 "TY1208Z_ETHERNET_INHERITED", "HI3798MV100_EMMC_READ_SAMPLES", "BLK_DEV",
                 "FS_ENCRYPTION", "FS_VERITY"}
    if set(active) & forbidden:
        raise ValueError("Prohibited subsystem in SD read-only profile")
    return True
