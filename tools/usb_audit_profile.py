"""Exact resource/config gate for a standalone read-only USB register audit."""
import re

RESOURCES = [0xf8a220b8, 4, 0xf8a220bc, 4, 0xf8a20120, 4, 0xf8a20124, 4,
             0xf8000ee0, 4, 0xf9890000, 0x10000, 0xf9880000, 0x10000]


def usb_audit_profile(tree, config):
    nodes = [node for node in tree["nodes"] if node["path"] == "/soc/usb-audit@f9890000"]
    enabled = "CONFIG_HI3798MV100_USB_AUDIT=y\n" in config
    if not enabled:
        if nodes:
            raise ValueError("USB audit node outside its explicit profile")
        return False
    if len(nodes) != 1 or 'CONFIG_LOCALVERSION="-ty1208z-usb-audit1"\n' not in config:
        raise ValueError("Unexpected USB audit node/release")
    props = nodes[0]["properties"]
    if (props.get("compatible", {}).get("strings") != ["tianyi,ty1208z-usb-register-audit"] or
            props.get("reg", {}).get("cells") != RESOURCES or set(props) != {"compatible", "reg"}):
        raise ValueError("USB audit resources or properties differ")
    paths = {node["path"] for node in tree["nodes"]}
    expected_paths = {"/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
                      "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
                      "/soc/timer@f8a29000", "/soc/serial@f8b00000", "/soc/usb-audit@f9890000"}
    if paths != expected_paths:
        raise ValueError("Unreviewed peripheral in USB audit profile")
    root = next(node["properties"] for node in tree["nodes"] if node["path"] == "/")
    if root.get("compatible", {}).get("strings") != ["tianyi,ty1208z-ca-diagnostic", "hi3798mv100-series"]:
        raise ValueError("Unexpected USB audit board identity")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    prohibited = {"USB_SUPPORT", "BLOCK", "MMC", "MTD", "ATA", "SCSI", "NET", "MODULES", "SMP",
                  "DEBUG_FS", "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT",
                  "HI3798MV100_ETHERNET_AUDIT", "HI3798MV100_ETHERNET_CLOCK_ID",
                  "TY1208Z_ETHERNET_INHERITED"}
    if active & prohibited:
        raise ValueError("Prohibited subsystem in USB audit: " + ", ".join(sorted(active & prohibited)))
    return True
