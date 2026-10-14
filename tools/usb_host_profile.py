"""Exact host0 enumeration profile following the physical capability audit."""
import re

HOST_NODES = {
    "/soc/clock-controller@f8a220b8", "/soc/usb@f9890000", "/soc/usb@f9880000",
}
BASE_NODES = {
    "/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
    "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
    "/soc/timer@f8a29000", "/soc/serial@f8b00000",
}
CONTROLS = [0xf8a220b8, 4, 0xf8a220bc, 4, 0xf8a20120, 4, 0xf8a20124, 4, 0xf8000ee0, 4]
USB_OPTIONS = {
    "USB_SUPPORT", "USB_COMMON", "USB_ARCH_HAS_HCD", "USB",
    "USB_EHCI_HCD", "USB_EHCI_HCD_PLATFORM", "USB_EHCI_TT_NEWSCHED",
    "USB_OHCI_HCD", "USB_OHCI_HCD_PLATFORM", "USB_OHCI_LITTLE_ENDIAN",
}


def validate_usb_resources(props):
    """Check the measured shared-clock connection in either explicit profile."""
    clock = props["/soc/clock-controller@f8a220b8"]
    if (set(clock) != {"compatible", "reg", "#clock-cells", "phandle"} or
            clock["compatible"].get("strings") != ["tianyi,ty1208z-usb-host0-clock"] or
            clock["reg"].get("cells") != CONTROLS or clock["#clock-cells"].get("cells") != [0]):
        raise ValueError("USB host0 clock resources or properties differ")
    phandle = clock["phandle"].get("cells")
    if not phandle or len(phandle) != 1 or phandle[0] in (0, 0xffffffff):
        raise ValueError("Missing USB host0 shared clock phandle")
    for path, compatible, address, irq in (
        ("/soc/usb@f9890000", "generic-ehci", 0xf9890000, 66),
        ("/soc/usb@f9880000", "generic-ohci", 0xf9880000, 67),
    ):
        host = props[path]
        if (set(host) != {"compatible", "reg", "interrupts", "clocks"} or
                host["compatible"].get("strings") != [compatible] or
                host["reg"].get("cells") != [address, 0x10000] or
                host["interrupts"].get("cells") != [0, irq, 4] or
                host["clocks"].get("cells") != phandle):
            raise ValueError("USB host0 HCD resource/IRQ/shared-clock connection differs")


def usb_host_profile(tree, config):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    enabled = "CONFIG_TY1208Z_USB_HOST0_EXPERIMENT=y\n" in config
    nodes = props.keys() & HOST_NODES
    if not enabled:
        if nodes:
            raise ValueError("USB host resources outside the explicit host0 profile")
        return False
    if (set(props) != BASE_NODES | HOST_NODES or
            'CONFIG_LOCALVERSION="-ty1208z-usb-host1"\n' not in config or
            props["/"].get("compatible", {}).get("strings") != [
                "tianyi,ty1208z-ca-usb-host-experiment", "hi3798mv100-series"]):
        raise ValueError("USB host0 identity, nodes or kernel release differs")
    if props["/memory@0"].get("reg", {}).get("cells") != [0, 0x10000000]:
        raise ValueError("USB host0 experiment exceeds bounded low RAM")
    validate_usb_resources(props)
    values = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", config, re.MULTILINE))
    active = set(values)
    if any(values.get(name) != "y" for name in USB_OPTIONS):
        raise ValueError("Missing built-in USB host0 option")
    unexpected_usb = {name for name in active if name.startswith("USB")} - USB_OPTIONS
    prohibited = {
        "BLOCK", "MMC", "MTD", "ATA", "SCSI", "NET", "MODULES", "SMP", "PM", "DEBUG_FS",
        "HID", "INPUT", "SOUND", "MEDIA_SUPPORT", "GENERIC_PHY", "USB_PHY",
        "HI3798MV100_USB_AUDIT", "HI3798MV100_EMMC_AUDIT", "MMC_DW_HI3798MV100_IDENT",
        "HI3798MV100_ETHERNET_AUDIT", "HI3798MV100_ETHERNET_CLOCK_ID",
        "TY1208Z_ETHERNET_INHERITED", "POWER_RESET_TY1208Z_SP805",
    }
    if unexpected_usb or active & prohibited:
        raise ValueError("Unexpected USB host0 subsystem: " +
                         ", ".join(sorted(unexpected_usb | (active & prohibited))))
    return True
