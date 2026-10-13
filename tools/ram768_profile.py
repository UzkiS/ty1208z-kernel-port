"""Independent bounded memory experiment; all peripherals but UART/timer/reset denied."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

END = 0x30000000
NODE = "/soc/ram-restart@f8a2c000"
IDENTITY = ["tianyi,ty1208z-ca-ram768", "hi3798mv100-series"]
ALLOCATIONS = [(0x3FBFD000, 4194304), (0x3F8FC000, 3145728),
               (0x3F87B000, 524288), (0x3F878000, 8192), (0x3F843000, 212992),
               (0x3F742000, 1048576), (0x3F73E000, 12288), (0x3EF54000, 8294400),
               (0x3EDBE000, 1658880), (0x3E5D4000, 8294400), (0x3E507000, 835584)]
BASE = {"/", "/aliases", "/chosen", "/memory@0", "/cpus", "/cpus/cpu@0",
        "/clock-24m", "/clock-83m3", "/interrupt-controller@f8a01000", "/soc",
        "/soc/timer@f8a29000", "/soc/serial@f8b00000"}
RESOURCES = {
    "/soc/timer@f8a29000": {"reg": [0xf8a29000, 0x20, 0xf8a2a000, 0x20], "interrupts": [0, 26, 4]},
    "/soc/serial@f8b00000": {"reg": [0xf8b00000, 0x1000], "interrupts": [0, 49, 4]},
    "/interrupt-controller@f8a01000": {"reg": [0xf8a01000, 0x1000, 0xf8a02000, 0x100]},
    "/clock-24m": {"clock-frequency": [24000000]},
    "/clock-83m3": {"clock-frequency": [83300000]},
    "/cpus/cpu@0": {"reg": [0]},
}


def ram768_profile(tree, config):
    props = {node["path"]: node["properties"] for node in tree["nodes"]}
    identity = props.get("/", {}).get("compatible", {}).get("strings")
    active = set(re.findall(r"^CONFIG_(\w+)=[ym]$", config, re.MULTILINE))
    if "POWER_RESET_TY1208Z_MV100_RAM" not in active:
        if identity == IDENTITY or NODE in props:
            raise ValueError("Memory experiment without its exact reset configuration")
        return False
    if (identity != IDENTITY or set(props) != BASE | {NODE} or
            'CONFIG_LOCALVERSION="-ty1208z-ram768"\n' not in config or
            props["/memory@0"].get("reg", {}).get("cells") != [0, END]):
        raise ValueError("Unexpected memory experiment identity/RAM/peripheral")
    reset = props[NODE]
    if (set(reset) != {"compatible", "reg"} or
            reset["compatible"].get("strings") != ["tianyi,ty1208z-mv100-ram-restart"] or
            reset["reg"].get("cells") != [0xf8a2c000, 0x1000, 0xf8000ee0, 4]):
        raise ValueError("Unexpected memory restart resources")
    for node, fields in RESOURCES.items():
        for field, cells in fields.items():
            if props[node].get(field, {}).get("cells") != cells:
                raise ValueError("Memory experiment UART/timer/GIC/CPU/clock differs")
    forbidden = {"WATCHDOG", "HIGHMEM", "NET", "BLOCK", "MMC", "MTD", "USB_SUPPORT", "TY1208Z_ROUTER_RAM768",
                 "MODULES", "SMP", "DEBUG_FS", "PM", "ATA", "SCSI", "PCI"}
    other = {option for option in active if option.startswith(("HI3798MV100_", "POWER_RESET_"))} - {
        "HI3798MV100_TIMER", "POWER_RESET_HISI", "POWER_RESET_TY1208Z_MV100_RAM"}
    if active & forbidden or other or not {"POWER_RESET", "PROC_PAGE_MONITOR", "TMPFS"} <= active:
        raise ValueError("Unreviewed memory experiment subsystem")
    return True


def memory_boot_evidence(path, inspection=None):
    """Require the actual fresh reboot table, independently hash-verified."""
    path = Path(path)
    record = json.loads(path.read_bytes())
    raw = path.with_suffix(".rx").read_bytes()
    if (record.get("status") != "restart-bootloader-verified" or
            not record.get("restart_sent") or record.get("persistent_writes") is not False or
            record.get("raw_sha256") != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Fresh command-restart memory evidence missing or corrupt")
    # Exclude the old Linux report before the actual reboot.
    boot = raw[raw.rfind(b"Bootrom start"):]
    if (not boot.startswith(b"Bootrom start") or b"DDR Size:      1GB" not in boot or
            b"CPU:           Hi3798Mv100 (CA)" not in boot):
        raise ValueError("Fresh 1-GiB CA boot identity missing")
    allocations = [(int(address, 16), int(size)) for address, size in re.findall(
        rb"^[ \t]*(0x[0-9a-fA-F]+)[ \t]+(\d+)[ \t]*\r?$", boot, re.MULTILINE)]
    if allocations != ALLOCATIONS or b"Free  Addr:          0x3E507000" not in boot:
        raise ValueError("Fresh loader allocations changed; memory extension denied")
    if any(start < END or start + length > 0x40000000 for start, length in allocations):
        raise ValueError("Memory extension overlaps measured loader allocations")
    if inspection is not None:
        gap = (datetime.fromisoformat(inspection["started_utc"]) -
               datetime.fromisoformat(record["ended_utc"])).total_seconds()
        if not 0 <= gap <= 120 or inspection.get("port") != record.get("port"):
            raise ValueError("Memory allocation evidence is not from the immediately preceding reboot")
    return record["raw_sha256"]
