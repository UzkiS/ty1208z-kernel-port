#!/usr/bin/env python3
"""Checked opt-in p6/p9 write changes over the accepted read-only system tree."""
from pathlib import Path

CHANGES = {
    "drivers/mmc/core/mmc.c": [(
        '\t\t\t\tEXT_CSD_CACHE_CTRL, 1, timeout_ms);',
        '\t\t\t\tEXT_CSD_CACHE_CTRL,\n'
        '\t\t\t\tIS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE) ? 0 : 1,\n'
        '\t\t\t\ttimeout_ms);'), (
        '\t\t\tcard->ext_csd.cache_ctrl = 1;',
        '\t\t\tcard->ext_csd.cache_ctrl =\n'
        '\t\t\t\t!IS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE);')],
    "arch/arm/mach-hisi/Kconfig": [(
        "config TY1208Z_OPENWRT_SYSTEM\n",
        'config TY1208Z_EMMC_INSTALL_CANDIDATE\n'
        '\tbool "TY1208Z opt-in p6/p9 eMMC installation candidate"\n'
        '\tdepends on TY1208Z_OPENWRT_SYSTEM && HI3798MV100_EMMC_READ_ONLY\n'
        '\thelp\n'
        '\t  Permit one-sector user-area writes only to measured p6/p9.\n'
        '\t  Installation and persistent boot require separate authorization.\n\n'
        'config TY1208Z_OPENWRT_SYSTEM\n')],
    "drivers/mmc/core/block.c": [(
        '\treturn IS_ENABLED(CONFIG_HI3798MV100_EMMC_READ_ONLY) ||\n',
        '\treturn (IS_ENABLED(CONFIG_HI3798MV100_EMMC_READ_ONLY) &&\n'
        '\t\t(!IS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE) ||\n'
        '\t\t !mmc_card_mmc(card))) ||\n')],
    "drivers/mmc/core/queue.c": [(
        '\tlim.max_hw_sectors = min(host->max_blk_count, host->max_req_size / 512);',
        '\tlim.max_hw_sectors = min(host->max_blk_count, host->max_req_size / 512);\n'
        '\t/* Block queues require a page; block.c trims each transfer to\n'
        '\t * max_blk_count and completes/requeues the remaining sectors.\n'
        '\t */\n'
        '\tif (IS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE) &&\n'
        '\t    mmc_card_mmc(card) && host->max_blk_count == 1)\n'
        '\t\tlim.max_hw_sectors = max(lim.max_hw_sectors, PAGE_SIZE / 512);')],
    "drivers/mmc/host/dw_mmc-hi3798mv100-ident.c": [(
        '#include "hi3798mv100-emmc-ro-policy.h"\n',
        '#include "hi3798mv100-emmc-ro-policy.h"\n'
        '#include "hi3798mv100-emmc-install-policy.h"\n'), (
        '\tmmc->max_blk_count = IS_ENABLED(CONFIG_HI3798MV100_EMMC_READ_ONLY) ? 8 : 1;',
        '\tmmc->max_blk_count = IS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE) ? 1 :\n'
        '\t\t(IS_ENABLED(CONFIG_HI3798MV100_EMMC_READ_ONLY) ? 8 : 1);'), (
        '\tmmc->max_req_size = 512 * mmc->max_blk_count;',
        '\t/* A block queue must accept a page, while each MMC transfer stays\n'
        '\t * one sector via max_blk_count and the request policy.\n'
        '\t */\n'
        '\tmmc->max_req_size = IS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE) ?\n'
        '\t\tPAGE_SIZE : 512 * mmc->max_blk_count;'), (
        '\t\tret = hi3798mv100_emmc_ro_request(mrq, user_area, sectors);',
        '\t\tif (IS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE))\n'
        '\t\t\tret = hi3798mv100_emmc_install_request(mrq, user_area, sectors);\n'
        '\t\telse\n'
        '\t\t\tret = hi3798mv100_emmc_ro_request(mrq, user_area, sectors);'), (
        '\t.force_ro = IS_ENABLED(CONFIG_HI3798MV100_EMMC_READ_ONLY),',
        '\t.force_ro = IS_ENABLED(CONFIG_HI3798MV100_EMMC_READ_ONLY) &&\n'
        '\t\t    !IS_ENABLED(CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE),')],
}


def ensure(text, name):
    for before, after in CHANGES.get(name, []):
        if text.count(after) == 1:
            continue
        if text.count(before) != 1:
            raise ValueError("Persistent kernel anchor changed: " + name)
        text = text.replace(before, after)
    return text


def apply(kernel, project):
    for name in CHANGES:
        path = kernel / name
        path.write_text(ensure(path.read_text(), name))
    relative = Path("drivers/mmc/host/hi3798mv100-emmc-install-policy.h")
    (kernel / relative).write_bytes((project / "overlay" / relative).read_bytes())
