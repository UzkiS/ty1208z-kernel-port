#!/usr/bin/env python3
"""Execute actual native SD audit registration/probe-unwind/removal paths."""
from pathlib import Path
import subprocess
import tempfile

from test_restart_module import HARNESS, MAIN

ROOT = Path(__file__).resolve().parents[1]


def test():
    source = (ROOT / "overlay/drivers/soc/hisilicon/hi3798mv100-sd-audit.c").read_text()
    harness = HARNESS.replace("ty1208z_restart", "hi3798mv100_sd_audit")
    harness = harness.replace('"ty1208z-sp805-restart"', '"hi3798mv100-sd-audit"')
    before = ("assert(count == 2 && res[0].start == 0xf8a2c000 && res[0].end == 0xf8a2cfff);\n"
              "    assert(res[1].start == 0xf8000ee0 && res[1].end == 0xf8000ee3);\n"
              "    assert(res[0].flags == IORESOURCE_MEM && res[1].flags == IORESOURCE_MEM);")
    after = ("assert(count == 3 && res[0].start == 0xf9820000 && res[0].end == 0xf9820fff);\n"
             "    assert(res[1].start == 0xf8a2209c && res[1].end == 0xf8a2209f);\n"
             "    assert(res[2].start == 0xf8a2011c && res[2].end == 0xf8a2011f);\n"
             "    for (unsigned i = 0; i < count; i++) assert(res[i].flags == IORESOURCE_MEM);")
    assert harness.count(before) == 1
    harness = harness.replace(before, after)
    main = MAIN.replace("ty1208z_ram_restart", "hi3798mv100_ram_sd_audit")
    main = main.replace("SP805_RAM_MODULE_LIFECYCLE_PASS", "SD_AUDIT_RAM_MODULE_LIFECYCLE_PASS")
    start = source.index("static int __init hi3798mv100_ram_sd_audit_init(void)")
    end = source.index("module_init(hi3798mv100_ram_sd_audit_init);", start)
    exit_start = source.index("static void __exit hi3798mv100_ram_sd_audit_exit(void)", end)
    exit_end = source.index("module_exit(hi3798mv100_ram_sd_audit_exit);", exit_start)
    with tempfile.TemporaryDirectory(prefix="sd-audit-module-") as directory:
        path = Path(directory)
        program = path / "test.c"
        program.write_text(harness + source[start:end] + source[exit_start:exit_end] + main)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(program), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    test()
