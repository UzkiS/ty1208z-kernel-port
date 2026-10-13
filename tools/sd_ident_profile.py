"""Exact SD metadata-only profile with separately guarded measured restart."""
import re

from sd_audit_profile import BASE_PATHS

NODE = "/soc/mmc@f9820000"
RESTART = "/soc/sd-restart@f8a2c000"
CONFIG = 'CONFIG_LOCALVERSION="-ty1208z-sd-ident1"\n'
OPTIONS = {"MMC", "MMC_DW", "MMC_DW_PLTFM", "MMC_DW_HI3798MV100_SD_IDENT",
           "POWER_RESET", "POWER_RESET_TY1208Z_MV100_SD"}
PROPERTIES = {"compatible": {"strings": ["tianyi,ty1208z-sd-identification"]},
              "reg": {"cells": [0xf9820000, 0x1000, 0xf8a2209c, 4, 0xf8a2011c, 4]},
              "reg-names": {"strings": ["controller", "crg39", "ldo"]},
              "interrupts": {"cells": [0, 34, 4]}, "clock-frequency": {"cells": [50000000]},
              "fifo-depth": {"cells": [256]}, "bus-width": {"cells": [1]},
              "max-frequency": {"cells": [25000000]}, "no-mmc": {}, "no-sdio": {}}
RESTART_PROPERTIES = {"compatible": {"strings": ["tianyi,ty1208z-mv100-sd-ident-restart"]},
                      "reg": {"cells": [0xf8a2c000, 0x1000, 0xf8000ee0, 4]}}


def sd_ident_profile(tree, config):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    enabled = "CONFIG_MMC_DW_HI3798MV100_SD_IDENT=y\n" in config
    if not enabled:
        if NODE in props or RESTART in props or "CONFIG_POWER_RESET_TY1208Z_MV100_SD=y\n" in config:
            raise ValueError("SD identification/restart outside its explicit profile")
        return False
    if CONFIG not in config or set(props) != BASE_PATHS | {NODE, RESTART}:
        raise ValueError("Unexpected SD identification release/peripheral")
    if props["/"].get("compatible", {}).get("strings") != ["tianyi,ty1208z-ca-sd-ident-ram", "hi3798mv100-series"]:
        raise ValueError("Unexpected SD identification board identity")
    for node, expected in ((NODE, PROPERTIES), (RESTART, RESTART_PROPERTIES)):
        if set(props[node]) != set(expected):
            raise ValueError("Unreviewed SD identification/restart property")
        for name, value in expected.items():
            for kind, content in value.items():
                if props[node][name].get(kind) != content:
                    raise ValueError("SD identification resource/clock/bus differs")
    active = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", config, re.MULTILINE))
    if any(active.get(name) != "y" for name in OPTIONS):
        raise ValueError("Incomplete SD identification/restart configuration")
    restricted = {name for name in active if name.startswith(("MMC", "POWER_RESET_", "PWRSEQ_"))}
    if restricted - OPTIONS - {"POWER_RESET_HISI"}:
        raise ValueError("Unreviewed MMC/reset driver in SD identification")
    forbidden = {"BLOCK", "NET", "MODULES", "SMP", "USB_SUPPORT", "MTD", "ATA", "SCSI",
                 "WATCHDOG", "DEBUG_FS", "PM", "HI3798MV100_SD_AUDIT", "HI3798MV100_EMMC_AUDIT",
                 "TY1208Z_ETHERNET_INHERITED", "HI3798MV100_EMMC_READ_SAMPLES"}
    if set(active) & forbidden:
        raise ValueError("Prohibited subsystem in SD identification")
    return True
