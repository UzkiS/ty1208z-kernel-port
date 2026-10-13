"""Shared, narrow gate for the explicit card-identification RAM profile."""
import re


def identification_profile(tree, config):
    nodes = [node for node in tree["nodes"] if node["path"] == "/soc/mmc@f9830000"]
    enabled = "CONFIG_MMC_DW_HI3798MV100_IDENT=y\n" in config
    samples = "CONFIG_HI3798MV100_EMMC_READ_SAMPLES=y\n" in config
    if "CONFIG_HI3798MV100_EMMC_READ_ONLY=y\n" in config:
        raise ValueError("eMMC block experiment has no accepted RAM boot profile yet")
    if not enabled:
        if nodes or samples:
            raise ValueError("Identification node outside its explicit profile")
        return False
    release = "emmc-read1" if samples else "emmc-ident1"
    if len(nodes) != 1 or f'CONFIG_LOCALVERSION="-ty1208z-{release}"\n' not in config:
        raise ValueError("Unexpected identification node/release")
    props = nodes[0]["properties"]
    expected = {
        "reg": [0xf9830000, 0x1000, 0xf8a220a0, 4],
        "interrupts": [0, 35, 4], "clock-frequency": [100000000],
        "fifo-depth": [256], "bus-width": [1], "max-frequency": [25000000],
    }
    if props.get("compatible", {}).get("strings") != ["tianyi,ty1208z-emmc-identification"]:
        raise ValueError("Unexpected identification compatible")
    if any(props.get(key, {}).get("cells") != value for key, value in expected.items()):
        raise ValueError("Unexpected identification resource/clock/bus limits")
    if not all(key in props for key in ("non-removable", "no-sd", "no-sdio")):
        raise ValueError("Missing MMC-only identification constraints")
    allowed = set(expected) | {"compatible", "reg-names", "non-removable", "no-sd", "no-sdio"}
    if set(props) - allowed:
        raise ValueError("Unreviewed identification DT property")
    mmc_options = {"MMC", "MMC_DW", "MMC_DW_PLTFM", "MMC_DW_HI3798MV100_IDENT"}
    active = dict(re.findall(r"^CONFIG_(\w+)=([ym])$", config, re.MULTILINE))
    if any(active.get(option) != "y" for option in mmc_options):
        raise ValueError("Incomplete identification driver configuration")
    if any(option.startswith("MMC") and option not in mmc_options for option in active):
        raise ValueError("Unreviewed MMC subsystem enabled")
    prohibited = {"BLOCK", "MMC_TEST", "DEBUG_FS", "PWRSEQ_EMMC", "PWRSEQ_SIMPLE",
                  "HI3798MV100_EMMC_AUDIT", "MODULES", "NET", "USB_SUPPORT", "MTD", "SMP"}
    if active.keys() & prohibited:
        raise ValueError("Prohibited subsystem in identification profile")
    if samples and active.get("CRC32") != "y":
        raise ValueError("Fixed sector samples require the CRC32 library")
    if any(node["path"] == "/soc/emmc-audit@f9830000" for node in tree["nodes"]):
        raise ValueError("Conflicting register audit node")
    return True
