"""Exact isolated SP805 restart experiment; no watchdog device or storage."""
import re

NODE = "/soc/restart-controller@f8a2c000"


def restart_profile(tree, config):
    nodes = [node for node in tree["nodes"] if node["path"] == NODE]
    enabled = "CONFIG_POWER_RESET_TY1208Z_SP805=y\n" in config
    if not enabled:
        if nodes:
            raise ValueError("Restart controller outside its explicit profile")
        return False
    if len(nodes) != 1 or 'CONFIG_LOCALVERSION="-ty1208z-restart1"\n' not in config:
        raise ValueError("Unexpected restart node/release")
    props = nodes[0]["properties"]
    if (props.get("compatible", {}).get("strings") != ["tianyi,ty1208z-sp805-restart"] or
            props.get("reg", {}).get("cells") != [0xf8a2c000, 0x1000] or
            set(props) != {"compatible", "reg"}):
        raise ValueError("Restart resources or properties differ")
    expected = {"/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
                "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
                "/soc/timer@f8a29000", "/soc/serial@f8b00000", NODE}
    if {node["path"] for node in tree["nodes"]} != expected:
        raise ValueError("Unreviewed peripheral in restart profile")
    root = next(node["properties"] for node in tree["nodes"] if node["path"] == "/")
    if root.get("compatible", {}).get("strings") != ["tianyi,ty1208z-ca-diagnostic", "hi3798mv100-series"]:
        raise ValueError("Unexpected restart board identity")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    prohibited = {"WATCHDOG", "USB_SUPPORT", "BLOCK", "MMC", "MTD", "ATA", "SCSI", "NET",
                  "MODULES", "SMP", "DEBUG_FS", "HI3798MV100_USB_AUDIT",
                  "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT",
                  "HI3798MV100_ETHERNET_AUDIT", "HI3798MV100_ETHERNET_CLOCK_ID",
                  "TY1208Z_ETHERNET_INHERITED"}
    other_reset = {option for option in active if option.startswith("POWER_RESET_")} - {
        "POWER_RESET_TY1208Z_SP805", "POWER_RESET_HISI"}
    # ARCH_HISI unconditionally selects its generic reset driver. The exact
    # DT path/property gate above excludes every compatible it can bind to.
    if active & prohibited or other_reset or "POWER_RESET" not in active:
        raise ValueError("Invalid restart subsystem selection")
    return True
