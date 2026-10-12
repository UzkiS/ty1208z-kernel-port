#!/usr/bin/env python3
"""Generate the diagnostic patch from a verified, pristine Linux archive."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import tarfile

project = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--archive", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
lock = json.loads((project / "config/sources.lock.json").read_text())
with args.archive.open("rb") as source:
    assert hashlib.file_digest(source, "sha256").hexdigest() == lock["linux"]["sha256"]

changes = {
    "arch/arm/mach-hisi/Kconfig": (
        'config ARCH_HI3xxx\n',
        'config ARCH_HI3798MV100\n'
        '\tbool "Hi3798MV100 single-core diagnostic support"\n'
        '\tdepends on ARCH_MULTI_V7 && !SMP\n'
        '\tselect HI3798MV100_TIMER\n'
        '\thelp\n'
        '\t  Experimental RAM-only diagnostic candidate for TY1208Z CA.\n'
        '\t  Hardware boot and secure-boot acceptance remain unverified.\n\n'
        'config ARCH_HI3xxx\n'),
    "arch/arm/mach-hisi/Makefile": (
        'obj-y\t+= hisilicon.o\n',
        'obj-y\t+= hisilicon.o\nobj-$(CONFIG_ARCH_HI3798MV100) += hi3798mv100.o\n'),
    "arch/arm/boot/dts/hisilicon/Makefile": (
        '# SPDX-License-Identifier: GPL-2.0\n',
        '# SPDX-License-Identifier: GPL-2.0\n'
        'dtb-$(CONFIG_ARCH_HI3798MV100) += hi3798mv100-ty1208z-diagnostic.dtb\n'
        'dtb-$(CONFIG_MMC_DW_HI3798MV100_IDENT) += hi3798mv100-ty1208z-emmc-ident.dtb\n'
        'dtb-$(CONFIG_HI3798MV100_EMMC_AUDIT) += hi3798mv100-ty1208z-emmc-audit.dtb\n'),
    "drivers/soc/hisilicon/Kconfig": (
        'config KUNPENG_HCCS\n',
        'config HI3798MV100_EMMC_AUDIT\n'
        '\tbool "Read-only TY1208Z eMMC register audit"\n'
        '\tdepends on ARCH_HI3798MV100 && !MMC && !BLOCK\n'
        '\thelp\n'
        '\t  Read controller identification and clock registers only.\n'
        '\t  Does not initialize the card or change clock/reset state.\n\n'
        'config KUNPENG_HCCS\n'),
    "drivers/soc/hisilicon/Makefile": (
        '# SPDX-License-Identifier: GPL-2.0-only\n',
        '# SPDX-License-Identifier: GPL-2.0-only\n'
        'obj-$(CONFIG_HI3798MV100_EMMC_AUDIT) += hi3798mv100-emmc-audit.o\n'),
    "drivers/clocksource/Kconfig": (
        'config ARM_TIMER_SP804\n',
        'config HI3798MV100_TIMER\n'
        '\tbool\n\tdepends on ARM && OF\n'
        '\tselect CLKSRC_MMIO\n\tselect TIMER_OF\n\n'
        'config ARM_TIMER_SP804\n'),
    "drivers/clocksource/Makefile": (
        'obj-$(CONFIG_ARM_TIMER_SP804)',
        'obj-$(CONFIG_HI3798MV100_TIMER) += timer-hi3798mv100.o\n'
        'obj-$(CONFIG_ARM_TIMER_SP804)'),
}
changes.update({
    "drivers/mmc/core/mmc.c": [
        ('static struct attribute *mmc_std_attrs[] = {\n',
         '#include "ty1208z-ident.h"\n\n'
         'static struct attribute *mmc_std_attrs[] = {\n'
         '#ifdef CONFIG_MMC_DW_HI3798MV100_IDENT\n'
         '\t&dev_attr_ty1208z_ident.attr,\n'
         '#endif\n'),
    ],
    "drivers/mmc/host/Kconfig": (
        'config MMC_DW_HI3798CV200\n',
        'config MMC_DW_HI3798MV100_IDENT\n'
        '\tbool "TY1208Z restricted eMMC identification diagnostic"\n'
        '\tdepends on MMC_DW && ARCH_HI3798MV100 && !BLOCK\n'
        '\tselect MMC_DW_PLTFM\n'
        '\thelp\n'
        '\t  PIO, 1-bit, legacy identification only. Blocks card settings,\n'
        '\t  data writes, sector I/O and unknown card commands.\n\n'
        'config MMC_DW_HI3798CV200\n'),
    "drivers/mmc/host/Makefile": (
        'obj-$(CONFIG_MMC_DW_HI3798CV200)',
        'obj-$(CONFIG_MMC_DW_HI3798MV100_IDENT) += dw_mmc-hi3798mv100-ident.o\n'
        'obj-$(CONFIG_MMC_DW_HI3798CV200)'),
    "drivers/mmc/host/dw_mmc.h": [
        (' * @init: early implementation specific initialization.\n',
         ' * @init: early implementation specific initialization.\n'
         ' * @init_slot: final slot constraints before host registration.\n'
         ' * @validate_request: reject a request before hardware queueing.\n'
         ' * @force_pio: skip all DMA allocation and initialization.\n'),
        ('\tint\t\t(*init)(struct dw_mci *host);\n',
         '\tint\t\t(*init)(struct dw_mci *host);\n'
         '\tint\t\t(*init_slot)(struct dw_mci_slot *slot);\n'
         '\tint\t\t(*validate_request)(struct dw_mci *host,\n'
         '\t\t\t\t\t    struct mmc_request *mrq);\n'
         '\tbool\t\tforce_pio;\n'),
    ],
    "drivers/mmc/host/dw_mmc.c": [
        ('\tWARN_ON(slot->mrq);\n',
         '\t/* Reject restricted diagnostic requests before any hardware queue. */\n'
         '\tif (host->drv_data && host->drv_data->validate_request) {\n'
         '\t\tint ret = host->drv_data->validate_request(host, mrq);\n\n'
         '\t\tif (ret) {\n'
         '\t\t\tmrq->cmd->error = ret;\n'
         '\t\t\tif (mrq->data)\n'
         '\t\t\t\tmrq->data->error = ret;\n'
         '\t\t\tmmc_request_done(mmc, mrq);\n'
         '\t\t\treturn;\n'
         '\t\t}\n'
         '\t}\n\n'
         '\tWARN_ON(slot->mrq);\n'),
        ('\tdw_mci_get_cd(mmc);\n\n\tret = mmc_add_host(mmc);\n',
         '\tif (host->drv_data && host->drv_data->init_slot) {\n'
         '\t\tret = host->drv_data->init_slot(slot);\n'
         '\t\tif (ret)\n'
         '\t\t\tgoto err_host_allocated;\n'
         '\t}\n\n'
         '\tdw_mci_get_cd(mmc);\n\n\tret = mmc_add_host(mmc);\n'),
        ('\tstruct device *dev = host->dev;\n\n\t/*\n\t* Check tansfer mode',
         '\tstruct device *dev = host->dev;\n\n'
         '\tif (host->drv_data && host->drv_data->force_pio)\n'
         '\t\tgoto no_dma;\n\n'
         '\t/*\n\t* Check tansfer mode'),
        ('\t * receive ready and error such as transmit, receive timeout, crc error\n'
         '\t */\n'
         '\tmci_writel(host, INTMASK, SDMMC_INT_CMD_DONE | SDMMC_INT_DATA_OVER |\n'
         '\t\t   SDMMC_INT_TXDR | SDMMC_INT_RXDR |\n'
         '\t\t   DW_MCI_ERROR_FLAGS);\n',
         '\t * receive ready and error such as transmit, receive timeout, crc error\n'
         '\t */\n'
         '\t/* Restricted PIO enables FIFO interrupts only for actual data. */\n'
         '\tmci_writel(host, INTMASK, SDMMC_INT_CMD_DONE | SDMMC_INT_DATA_OVER |\n'
         '\t\t   DW_MCI_ERROR_FLAGS |\n'
         '\t\t   ((host->drv_data && host->drv_data->force_pio) ? 0 :\n'
         '\t\t    (SDMMC_INT_TXDR | SDMMC_INT_RXDR)));\n'),
    ],
})

diffs = []
with tarfile.open(args.archive) as archive:
    for path, replacements in changes.items():
        before = archive.extractfile(f'linux-{lock["linux"]["version"]}/{path}').read().decode()
        after = before
        if isinstance(replacements, tuple):
            replacements = [replacements]
        for old, new in replacements:
            assert after.count(old) == 1, f"Patch anchor not unique: {path}"
            after = after.replace(old, new)
        diffs.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{path}", f"b/{path}"))
for source in sorted((project / "overlay").rglob("*")):
    if source.is_file():
        path = source.relative_to(project / "overlay").as_posix()
        diffs.extend(difflib.unified_diff([], source.read_text().splitlines(True), "/dev/null", f"b/{path}"))
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("".join(diffs), encoding="utf-8", newline="\n")
print(f"Generated {args.output} from verified Linux {lock['linux']['version']}")
