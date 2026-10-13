"""Exact gate for the separate, command-free onboard SD register audit."""
import re

NODE = "/soc/sd-audit@f9820000"
RESOURCES = [0xf9820000, 0x1000, 0xf8a2209c, 4, 0xf8a2011c, 4]
BASE_PATHS = {"/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
              "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
              "/soc/timer@f8a29000", "/soc/serial@f8b00000"}


def sd_audit_profile(tree, config):
    nodes = [node for node in tree["nodes"] if node["path"] == NODE]
    enabled = "CONFIG_HI3798MV100_SD_AUDIT=y\n" in config
    if not enabled:
        if nodes:
            raise ValueError("SD audit node outside its explicit profile")
        return False
    if len(nodes) != 1 or 'CONFIG_LOCALVERSION="-ty1208z-sd-audit1"\n' not in config:
        raise ValueError("Unexpected SD audit node/release")
    props = nodes[0]["properties"]
    if (props.get("compatible", {}).get("strings") != ["tianyi,ty1208z-sd-register-audit"] or
            props.get("reg", {}).get("cells") != RESOURCES or set(props) != {"compatible", "reg"}):
        raise ValueError("SD audit resources or properties differ")
    if {node["path"] for node in tree["nodes"]} != BASE_PATHS | {NODE}:
        raise ValueError("Unreviewed peripheral in SD audit profile")
    root = next(node["properties"] for node in tree["nodes"] if node["path"] == "/")
    if root.get("compatible", {}).get("strings") != ["tianyi,ty1208z-ca-diagnostic", "hi3798mv100-series"]:
        raise ValueError("Unexpected SD audit board identity")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    prohibited = {"BLOCK", "MMC", "MTD", "ATA", "SCSI", "NET", "USB_SUPPORT", "MODULES", "SMP",
                  "DEBUG_FS", "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT",
                  "HI3798MV100_ETHERNET_AUDIT", "HI3798MV100_ETHERNET_CLOCK_ID",
                  "TY1208Z_ETHERNET_INHERITED", "HI3798MV100_USB_AUDIT",
                  "HI3798MV100_USB_CLOCK_AUDIT", "TY1208Z_USB_HOST0_EXPERIMENT",
                  "POWER_RESET_TY1208Z_SP805"}
    if active & prohibited:
        raise ValueError("Prohibited subsystem in SD audit: " + ", ".join(sorted(active & prohibited)))
    return True
