#!/usr/bin/env python3
"""Validate production storage sources; persistent packaging adds no host limits."""


def ensure(text, name):
    """Compatibility entry point for policy tests; no secondary source edits."""
    return text


def apply(kernel, project):
    kconfig = (kernel / "arch/arm/mach-hisi/Kconfig").read_text()
    if kconfig.count("config TY1208Z_EMMC_INSTALL_CANDIDATE\n") != 1:
        raise ValueError("Persistent delivery requires the current production board patch")
    for name in ("hi3798mv100-emmc-rw-policy.h", "hi3798mv100-sd-rw-policy.h",
                 "hi3798mv100-block-rw-policy.h"):
        relative = "drivers/mmc/host/" + name
        if (kernel / relative).read_bytes() != (project / "overlay" / relative).read_bytes():
            raise ValueError("Production storage policy differs: " + name)
