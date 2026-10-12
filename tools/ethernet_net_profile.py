"""Narrow RAM-placement permission for one measured Ethernet experiment."""
import re

NETWORK_NODES = {
    "/soc/clock-controller@f8a220cc",
    "/soc/mdio@f9841100",
    "/soc/mdio@f9841100/ethernet-phy@1",
    "/soc/ethernet@f9840000",
}


def ethernet_net_profile(tree, config):
    return _ethernet_profile(tree, config, "tianyi,ty1208z-ca-diagnostic", "-ty1208z-ethernet-net1")


def openwrt_ethernet_profile(tree, config):
    valid = _ethernet_profile(tree, config, "tianyi,ty1208z-ca-openwrt-net", "-ty1208z-openwrt-net")
    if not valid:
        return False
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    if (props["/chosen"].get("bootargs", {}).get("strings") != [
            "console=ttyAMA0,115200 earlycon=pl011,mmio32,0xf8b00000 rdinit=/init loglevel=7 panic=0"] or
            props["/memory@0"].get("reg", {}).get("cells") != [0, 0x10000000]):
        raise ValueError("Native Ethernet RAM-root command line/memory differs")
    return True


def _ethernet_profile(tree, config, board, release):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    enabled = "CONFIG_TY1208Z_ETHERNET_INHERITED=y\n" in config
    nodes = props.keys() & NETWORK_NODES
    if not enabled:
        if nodes:
            raise ValueError("Ethernet network nodes outside explicit profile")
        return False
    if nodes != NETWORK_NODES or f'CONFIG_LOCALVERSION="{release}"\n' not in config:
        raise ValueError("Unexpected Ethernet network nodes/release")
    if props["/"]["compatible"]["strings"] != [
            board, "hi3798mv100-series"]:
        raise ValueError("Unexpected Ethernet board compatible")
    clock = props["/soc/clock-controller@f8a220cc"]
    mdio = props["/soc/mdio@f9841100"]
    phy = props["/soc/mdio@f9841100/ethernet-phy@1"]
    mac = props["/soc/ethernet@f9840000"]
    expected = [
        (clock, "compatible", "strings", ["tianyi,ty1208z-inherited-ethernet-clock"]),
        (clock, "reg", "cells", [0xf8a220cc, 4, 0xf8a22120, 4, 0xf8a20008, 4,
                                  0xf8a20118, 4, 0xf8a20844, 4]),
        (clock, "#clock-cells", "cells", [0]),
        (mdio, "compatible", "strings", ["hisilicon,hisi-femac-mdio"]),
        (mdio, "reg", "cells", [0xf9841100, 8]),
        (mdio, "#address-cells", "cells", [1]),
        (mdio, "#size-cells", "cells", [0]),
        (phy, "compatible", "strings", ["ethernet-phy-id2066.9823"]),
        (phy, "reg", "cells", [1]),
        (mac, "compatible", "strings", ["hisilicon,hi3798mv100-femac-inherited"]),
        (mac, "reg", "cells", [0xf9840000, 0x400, 0xf9841300, 0x200]),
        (mac, "interrupts", "cells", [0, 71, 4]),
        (mac, "phy-mode", "strings", ["mii"]),
    ]
    for node, key, kind, value in expected:
        if node.get(key, {}).get(kind) != value:
            raise ValueError(f"Changed Ethernet resource/control: {key}")
    clock_phandle = clock.get("phandle", {}).get("cells")
    phy_phandle = phy.get("phandle", {}).get("cells")
    if not clock_phandle or not phy_phandle or len(clock_phandle) != 1 or len(phy_phandle) != 1:
        raise ValueError("Missing Ethernet clock/PHY phandle")
    if (mdio.get("clocks", {}).get("cells") != clock_phandle or
            mac.get("clocks", {}).get("cells") != clock_phandle or
            mac.get("phy-handle", {}).get("cells") != phy_phandle):
        raise ValueError("Changed Ethernet clock/PHY connection")
    for node, allowed in (
        (clock, {"compatible", "reg", "#clock-cells", "phandle"}),
        (mdio, {"compatible", "reg", "clocks", "#address-cells", "#size-cells"}),
        (phy, {"compatible", "reg", "phandle"}),
        (mac, {"compatible", "reg", "interrupts", "clocks", "phy-mode", "phy-handle"}),
    ):
        if set(node) != allowed:
            raise ValueError("Unreviewed Ethernet DT property")
    active = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", config, re.MULTILINE))
    required = {"NET", "INET", "PACKET", "NETDEVICES", "HISI_FEMAC",
                "MDIO_HISI_FEMAC", "PHYLIB", "FESTA_TY1208Z_PHY"}
    if any(active.get(name) != "y" for name in required):
        raise ValueError("Incomplete built-in Ethernet configuration")
    prohibited = {"BLOCK", "MMC", "MTD", "ATA", "SCSI", "USB_SUPPORT", "MODULES", "SMP",
                  "DEBUG_FS", "IPV6", "NETFILTER", "WIRELESS", "WLAN",
                  "HI3798MV100_ETHERNET_AUDIT", "HI3798MV100_ETHERNET_CLOCK_ID",
                  "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT"}
    prohibited.add("HI3798MV100_USB_AUDIT")
    if active.keys() & prohibited:
        raise ValueError("Prohibited subsystem in Ethernet network profile: " +
                         ", ".join(sorted(active.keys() & prohibited)))
    # No extra board peripherals may ride on the new NET permission.
    base_nodes = {"/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
                  "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
                  "/soc/timer@f8a29000", "/soc/serial@f8b00000"}
    if props.keys() != base_nodes | NETWORK_NODES:
        raise ValueError("Unreviewed node in Ethernet network profile")
    return True
