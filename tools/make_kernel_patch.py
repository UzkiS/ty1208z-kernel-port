#!/usr/bin/env python3
"""Generate the diagnostic patch from a verified, pristine Linux archive."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import tarfile
from femac_patch import replacements as femac_replacements, REPEATED_ANCHORS

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
        'dtb-$(CONFIG_HI3798MV100_EMMC_READ_SAMPLES) += hi3798mv100-ty1208z-emmc-read.dtb\n'
        'dtb-$(CONFIG_HI3798MV100_EMMC_AUDIT) += hi3798mv100-ty1208z-emmc-audit.dtb\n'
        'dtb-$(CONFIG_HI3798MV100_ETHERNET_AUDIT) += hi3798mv100-ty1208z-ethernet-audit.dtb\n'
        'dtb-$(CONFIG_HI3798MV100_ETHERNET_CLOCK_ID) += hi3798mv100-ty1208z-ethernet-clock-id.dtb\n'),
    "drivers/soc/hisilicon/Kconfig": (
        'config KUNPENG_HCCS\n',
        'config HI3798MV100_EMMC_AUDIT\n'
        '\tbool "Read-only TY1208Z eMMC register audit"\n'
        '\tdepends on ARCH_HI3798MV100 && !MMC && !BLOCK\n'
        '\thelp\n'
        '\t  Read controller identification and clock registers only.\n'
        '\t  Does not initialize the card or change clock/reset state.\n\n'
        'config HI3798MV100_ETHERNET_AUDIT\n'
        '\tbool "TY1208Z inherited Ethernet state and PHY ID audit"\n'
        '\tdepends on ARCH_HI3798MV100 && !NET && !MMC && !BLOCK\n'
        '\thelp\n'
        '\t  Observe fixed clock/reset registers. If already enabled, read\n'
        '\t  PHY 1 ID via bounded MDIO. No PHY/clock/reset or DMA writes.\n\n'
        'config HI3798MV100_ETHERNET_CLOCK_ID\n'
        '\tbool "TY1208Z temporary MAC clock enable and PHY ID"\n'
        '\tdepends on ARCH_HI3798MV100 && !NET && !MMC && !BLOCK\n'
        '\tdepends on !HI3798MV100_ETHERNET_AUDIT && !DEBUG_FS\n'
        '\thelp\n'
        '\t  Require measured state, enable only CRG51 bit 3, read PHY ID,\n'
        '\t  then restore the clock. No PHY reset, DMA or storage access.\n\n'
        'config KUNPENG_HCCS\n'),
    "drivers/soc/hisilicon/Makefile": (
        '# SPDX-License-Identifier: GPL-2.0-only\n',
        '# SPDX-License-Identifier: GPL-2.0-only\n'
        'obj-$(CONFIG_HI3798MV100_EMMC_AUDIT) += hi3798mv100-emmc-audit.o\n'
        'obj-$(CONFIG_HI3798MV100_ETHERNET_AUDIT) += hi3798mv100-ethernet-audit.o\n'
        'obj-$(CONFIG_HI3798MV100_ETHERNET_CLOCK_ID) += hi3798mv100-ethernet-clock-id.o\n'),
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
    "drivers/soc/hisilicon/Kconfig": (
        changes["drivers/soc/hisilicon/Kconfig"][0],
        changes["drivers/soc/hisilicon/Kconfig"][1].replace(
            'config KUNPENG_HCCS\n',
            'config HI3798MV100_USB_AUDIT\n'
            '\tbool "Read-only TY1208Z USB host0 register audit"\n'
            '\tdepends on ARCH_HI3798MV100 && !USB_SUPPORT && !BLOCK && !NET\n'
            '\tdepends on !MMC && !MODULES && !SMP && !DEBUG_FS\n'
            '\thelp\n'
            '\t  Observe host0 clock/PHY controls and SYSID0 only. Read fixed\n'
            '\t  EHCI/OHCI capability words only when inherited controls permit.\n'
            '\t  No clock/reset writes, USB transactions or firmware loading.\n\n'
            'config KUNPENG_HCCS\n')),
    "drivers/soc/hisilicon/Makefile": (
        changes["drivers/soc/hisilicon/Makefile"][0],
        changes["drivers/soc/hisilicon/Makefile"][1] +
        'obj-$(CONFIG_HI3798MV100_USB_AUDIT) += hi3798mv100-usb-audit.o\n'),
})
changes["arch/arm/boot/dts/hisilicon/Makefile"] = (
    changes["arch/arm/boot/dts/hisilicon/Makefile"][0],
    changes["arch/arm/boot/dts/hisilicon/Makefile"][1] +
    'dtb-$(CONFIG_HI3798MV100_USB_AUDIT) += hi3798mv100-ty1208z-usb-audit.dtb\n')

changes["arch/arm/boot/dts/hisilicon/Makefile"] = (
    changes["arch/arm/boot/dts/hisilicon/Makefile"][0],
    changes["arch/arm/boot/dts/hisilicon/Makefile"][1] +
    'dtb-$(CONFIG_POWER_RESET_TY1208Z_SP805) += hi3798mv100-ty1208z-restart.dtb\n')
changes["drivers/power/reset/Kconfig"] = (
    'config POWER_RESET_AS3722\n',
    'config POWER_RESET_TY1208Z_SP805\n'
    '\tbool "TY1208Z explicit SP805 system restart experiment"\n'
    '\tdepends on ARCH_HI3798MV100 && !WATCHDOG && !BLOCK && !NET\n'
    '\tdepends on !USB_SUPPORT && !MMC && !MODULES && !SMP\n'
    '\thelp\n'
    '\t  Read real SP805 IDs and require disabled inherited control.\n'
    '\t  Register a restart handler without startup writes or a watchdog\n'
    '\t  device. Only explicit system restart arms this short watchdog.\n\n'
    'config POWER_RESET_AS3722\n')
changes["drivers/power/reset/Makefile"] = (
    '# SPDX-License-Identifier: GPL-2.0\n',
    '# SPDX-License-Identifier: GPL-2.0\n'
    'obj-$(CONFIG_POWER_RESET_TY1208Z_SP805) += ty1208z-sp805-restart.o\n')

changes.update({
    "drivers/mmc/core/mmc.c": [
        ('static struct attribute *mmc_std_attrs[] = {\n',
         '#include "ty1208z-ident.h"\n\n'
         'static struct attribute *mmc_std_attrs[] = {\n'
         '#ifdef CONFIG_MMC_DW_HI3798MV100_IDENT\n'
         '\t&dev_attr_ty1208z_ident.attr,\n'
         '#endif\n'),
    ],
    "drivers/mmc/core/Makefile": (
        'obj-$(CONFIG_MMC)\t\t+= mmc_core.o\n',
        'obj-$(CONFIG_MMC)\t\t+= mmc_core.o\n'
        'obj-$(CONFIG_HI3798MV100_EMMC_READ_SAMPLES) += ty1208z-samples.o\n'),
    "drivers/mmc/host/Kconfig": (
        'config MMC_DW_HI3798CV200\n',
        'config HI3798MV100_EMMC_READ_SAMPLES\n'
        '\tbool "TY1208Z fixed four-sector read-only diagnostic"\n'
        '\tdepends on MMC_DW_HI3798MV100_IDENT && !BLOCK\n'
        '\tselect CRC32\n'
        '\thelp\n'
        '\t  Read only two sectors each of the measured Hinas kernel header\n'
        '\t  and ext4 superblock. No block interface or card-setting writes.\n\n'
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

changes["arch/arm/boot/dts/hisilicon/Makefile"] = (
    changes["arch/arm/boot/dts/hisilicon/Makefile"][0],
    changes["arch/arm/boot/dts/hisilicon/Makefile"][1] +
    'dtb-$(CONFIG_TY1208Z_ETHERNET_INHERITED) += hi3798mv100-ty1208z-ethernet-net.dtb\n')
changes.update({
    "drivers/clk/hisilicon/Kconfig": (
        '# SPDX-License-Identifier: GPL-2.0-only\n',
        '# SPDX-License-Identifier: GPL-2.0-only\n\n'
        'config TY1208Z_ETHERNET_INHERITED\n'
        '\tbool "TY1208Z inherited-PHY Ethernet RAM experiment"\n'
        '\tdepends on ARCH_HI3798MV100 && HISI_FEMAC && !BLOCK && !MMC\n'
        '\tdepends on !HI3798MV100_ETHERNET_AUDIT && !HI3798MV100_ETHERNET_CLOCK_ID\n'
        '\thelp\n'
        '\t  Enable the measured MAC clock bit, preserving PHY controls.\n'
        '\t  No PHY reset/firmware or complete cold-start support.\n\n'),
    "drivers/clk/hisilicon/Makefile": (
        '# SPDX-License-Identifier: GPL-2.0\n',
        '# SPDX-License-Identifier: GPL-2.0\n'
        'obj-$(CONFIG_TY1208Z_ETHERNET_INHERITED) += clk-ty1208z-ethernet.o\n'),
    "drivers/net/phy/Kconfig": (
        'config FIXED_PHY\n',
        'config FESTA_TY1208Z_PHY\n'
        '\tbool "TY1208Z FESTAv220 inherited state"\n'
        '\tdepends on TY1208Z_ETHERNET_INHERITED && PHYLIB\n'
        '\thelp\n'
        '\t  Explicit no-reset experiment using measured PHY 0x20669823.\n'
        '\t  Uses generic 10/100 negotiation, no expanded-register fixup.\n\n'
        'config FIXED_PHY\n'),
    "drivers/net/phy/Makefile": (
        '# SPDX-License-Identifier: GPL-2.0\n',
        '# SPDX-License-Identifier: GPL-2.0\n'
        'obj-$(CONFIG_FESTA_TY1208Z_PHY) += festa-ty1208z.o\n'),
    "drivers/net/ethernet/hisilicon/hisi_femac.c": femac_replacements(),
})

changes["drivers/clk/hisilicon/Kconfig"] = (
    changes["drivers/clk/hisilicon/Kconfig"][0],
    changes["drivers/clk/hisilicon/Kconfig"][1] +
    'config TY1208Z_USB_HOST0_EXPERIMENT\n'
    '\tbool "TY1208Z USB host0 clock/PHY compile experiment"\n'
    '\tdepends on ARCH_HI3798MV100 && USB_EHCI_HCD_PLATFORM=y\n'
    '\tdepends on USB_OHCI_HCD_PLATFORM=y && !BLOCK && !MMC && !MTD\n'
    '\tdepends on !NET && !MODULES && !PM && !SMP && !DEBUG_FS\n'
    '\thelp\n'
    '\t  Optional shared host0 clock provider for an independent experiment.\n'
    '\t  Not enabled by any RAM image. Requires a separate reviewed board\n'
    '\t  identity/DT after hardware control and capability measurements.\n\n')
changes["drivers/clk/hisilicon/Makefile"] = (
    changes["drivers/clk/hisilicon/Makefile"][0],
    changes["drivers/clk/hisilicon/Makefile"][1] +
    'obj-$(CONFIG_TY1208Z_USB_HOST0_EXPERIMENT) += clk-ty1208z-usb.o\n')

diffs = []
with tarfile.open(args.archive) as archive:
    for path, replacements in changes.items():
        before = archive.extractfile(f'linux-{lock["linux"]["version"]}/{path}').read().decode()
        after = before
        if isinstance(replacements, tuple):
            replacements = [replacements]
        for old, new in replacements:
            count = REPEATED_ANCHORS.get(old, 1) if path.endswith("hisi_femac.c") else 1
            assert after.count(old) == count, f"Patch anchor changed: {path}: {old!r}"
            after = after.replace(old, new)
        diffs.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{path}", f"b/{path}"))
for source in sorted((project / "overlay").rglob("*")):
    if source.is_file():
        path = source.relative_to(project / "overlay").as_posix()
        diffs.extend(difflib.unified_diff([], source.read_text().splitlines(True), "/dev/null", f"b/{path}"))
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("".join(diffs), encoding="utf-8", newline="\n")
print(f"Generated {args.output} from verified Linux {lock['linux']['version']}")
