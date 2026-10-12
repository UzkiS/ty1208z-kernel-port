"""Validate the explicit inherited-state-only Ethernet diagnostic profile."""
import re


def ethernet_audit_profile(tree, config):
    nodes = [node for node in tree["nodes"] if node["path"] == "/soc/ethernet-audit@f9840000"]
    enabled = "CONFIG_HI3798MV100_ETHERNET_AUDIT=y\n" in config
    if not enabled:
        if nodes:
            raise ValueError("Ethernet audit node outside its explicit profile")
        return False
    if len(nodes) != 1 or 'CONFIG_LOCALVERSION="-ty1208z-ethernet-audit1"\n' not in config:
        raise ValueError("Unexpected Ethernet audit node/release")
    props = nodes[0]["properties"]
    if props.get("compatible", {}).get("strings") != ["tianyi,ty1208z-ethernet-audit"]:
        raise ValueError("Unexpected Ethernet audit compatible")
    expected = [0xf9840000, 0x4000, 0xf8a220cc, 4, 0xf8a22120, 4,
                0xf8a20008, 4, 0xf8a20118, 4, 0xf8a20844, 4]
    if props.get("reg", {}).get("cells") != expected:
        raise ValueError("Unexpected Ethernet audit resource layout")
    if props.get("reg-names", {}).get("strings") != [
            "mac", "crg51", "phy-crg", "phy-select", "phy-address", "phy-ldo"]:
        raise ValueError("Unexpected Ethernet audit resource names")
    if set(props) != {"compatible", "reg", "reg-names"}:
        raise ValueError("Unreviewed Ethernet audit DT property")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    prohibited = {"BLOCK", "MMC", "MTD", "NET", "USB_SUPPORT", "MODULES", "SMP",
                  "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT", "DEBUG_FS",
                  "HI3798MV100_ETHERNET_CLOCK_ID"}
    if active & prohibited:
        raise ValueError("Prohibited subsystem in Ethernet audit")
    return True


def ethernet_clock_id_profile(tree, config):
    nodes = [node for node in tree["nodes"] if node["path"] == "/soc/ethernet-clock-id@f9841100"]
    enabled = "CONFIG_HI3798MV100_ETHERNET_CLOCK_ID=y\n" in config
    if not enabled:
        if nodes:
            raise ValueError("Ethernet clock-ID node outside its explicit profile")
        return False
    if len(nodes) != 1 or 'CONFIG_LOCALVERSION="-ty1208z-ethernet-clock-id1"\n' not in config:
        raise ValueError("Unexpected Ethernet clock-ID node/release")
    props = nodes[0]["properties"]
    if props.get("compatible", {}).get("strings") != ["tianyi,ty1208z-ethernet-clock-id"]:
        raise ValueError("Unexpected Ethernet clock-ID compatible")
    expected = [0xf9841100, 8, 0xf8a220cc, 4, 0xf8a22120, 4,
                0xf8a20008, 4, 0xf8a20118, 4, 0xf8a20844, 4]
    if props.get("reg", {}).get("cells") != expected:
        raise ValueError("Unexpected Ethernet clock-ID resource layout")
    if props.get("reg-names", {}).get("strings") != [
            "mdio", "crg51", "phy-crg", "phy-select", "phy-address", "phy-ldo"]:
        raise ValueError("Unexpected Ethernet clock-ID resource names")
    if set(props) != {"compatible", "reg", "reg-names"}:
        raise ValueError("Unreviewed Ethernet clock-ID DT property")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    prohibited = {"BLOCK", "MMC", "MTD", "NET", "USB_SUPPORT", "MODULES", "SMP",
                  "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT", "DEBUG_FS",
                  "HI3798MV100_ETHERNET_AUDIT"}
    if active & prohibited:
        raise ValueError("Prohibited subsystem in Ethernet clock-ID")
    return True
