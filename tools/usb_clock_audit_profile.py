"""Exact standalone clock/capability experiment; no USB host stack."""
import re

from usb_audit_profile import RESOURCES

NODE = "/soc/usb-clock-audit@f9890000"
BASE_PATHS = {"/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
              "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
              "/soc/timer@f8a29000", "/soc/serial@f8b00000"}


def usb_clock_audit_profile(tree, config):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    board = props["/"].get("compatible", {}).get("strings", [])
    enabled = "CONFIG_HI3798MV100_USB_CLOCK_AUDIT=y\n" in config
    if not enabled:
        if NODE in props or "tianyi,ty1208z-ca-usb-clock-audit" in board:
            raise ValueError("USB clock experiment outside its explicit profile")
        return False
    if (set(props) != BASE_PATHS | {NODE} or
            board != ["tianyi,ty1208z-ca-usb-clock-audit", "hi3798mv100-series"] or
            'CONFIG_LOCALVERSION="-ty1208z-usb-clock-audit1"\n' not in config):
        raise ValueError("USB clock experiment identity, nodes or release differs")
    audit = props[NODE]
    if (set(audit) != {"compatible", "reg"} or audit["reg"].get("cells") != RESOURCES or
            audit["compatible"].get("strings") != ["tianyi,ty1208z-usb-clock-capability-audit"]):
        raise ValueError("USB clock experiment resources differ")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    prohibited = {"USB_SUPPORT", "NET", "BLOCK", "MMC", "MTD", "ATA", "SCSI", "MODULES",
                  "SMP", "DEBUG_FS", "HI3798MV100_USB_AUDIT", "TY1208Z_USB_HOST0_EXPERIMENT",
                  "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT",
                  "HI3798MV100_ETHERNET_AUDIT", "HI3798MV100_ETHERNET_CLOCK_ID",
                  "TY1208Z_ETHERNET_INHERITED", "POWER_RESET_TY1208Z_SP805"}
    if active & prohibited:
        raise ValueError("Unexpected USB clock experiment subsystem: " + ", ".join(sorted(active & prohibited)))
    return True
