"""Exact additive native-system changes; baseline profiles remain unchanged."""
TRANSFORMATIONS = {'arch/arm/mach-hisi/Kconfig': [('config TY1208Z_ROUTER_EMMC_RO\n',
                                 'config TY1208Z_OPENWRT_SYSTEM\n'
                                 '\tbool "TY1208Z native OpenWrt system with measured memory and '
                                 'read-only storage"\n'
                                 '\tdepends on ARCH_HI3798MV100 && NET && BLOCK && MMC\n'
                                 '\tdepends on !HIGHMEM && !SMP && !MTD\n'
                                 '\tdepends on !DEBUG_FS && !WATCHDOG && !PM\n'
                                 '\thelp\n'
                                 '\t  Integrate the measured 768-MiB memory, Ethernet, SD and eMMC '
                                 'paths.\n'
                                 '\t  Both storage controllers retain their existing request-level '
                                 'write denial.\n'
                                 '\n'
                                 'config TY1208Z_ROUTER_EMMC_RO\n')],
 'arch/arm/mm/init.c': [('#if IS_ENABLED(CONFIG_POWER_RESET_TY1208Z_MV100_RAM) || '
                         'IS_ENABLED(CONFIG_TY1208Z_ROUTER_RAM768) || '
                         'IS_ENABLED(CONFIG_TY1208Z_ROUTER_SD_RO) || '
                         'IS_ENABLED(CONFIG_TY1208Z_ROUTER_EMMC_RO)\n',
                         '#if IS_ENABLED(CONFIG_POWER_RESET_TY1208Z_MV100_RAM) || '
                         'IS_ENABLED(CONFIG_TY1208Z_ROUTER_RAM768) || '
                         'IS_ENABLED(CONFIG_TY1208Z_ROUTER_SD_RO) || '
                         'IS_ENABLED(CONFIG_TY1208Z_ROUTER_EMMC_RO) || '
                         'IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM)\n'),
                        ('\t     '
                         'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram"))) {',
                         '\t     of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")) '
                         '||\n'
                         '\t    (IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM) &&\n'
                         '\t     '
                         'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-system-ram"))) {')],
 'drivers/mmc/host/Kconfig': [('\tdepends on (!NET && !MODULES) || TY1208Z_ROUTER_EMMC_RO\n',
                               '\tdepends on (!NET && !MODULES) || TY1208Z_ROUTER_EMMC_RO || '
                               'TY1208Z_OPENWRT_SYSTEM\n')],
 'drivers/mmc/core/block.c': [('\tdevidx = ida_alloc_max(&mmc_blk_ida, max_devices - 1, '
                               'GFP_KERNEL);',
                               '\t/* Pin the two integrated read-only disks to the measured DT '
                               'host aliases. */\n'
                               '\tif (IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM))\n'
                               '\t\tdevidx = ida_alloc_range(&mmc_blk_ida, card->host->index,\n'
                               '\t\t\t\t\tcard->host->index, GFP_KERNEL);\n'
                               '\telse\n'
                               '\t\tdevidx = ida_alloc_max(&mmc_blk_ida, max_devices - 1, '
                               'GFP_KERNEL);')],
 'drivers/power/reset/Kconfig': [('config POWER_RESET_HISI\n',
                                  'config POWER_RESET_TY1208Z_MV100_SYSTEM\n'
                                  '\tbool "TY1208Z integrated SD/eMMC guarded RAM restart"\n'
                                  '\tdepends on TY1208Z_OPENWRT_SYSTEM\n'
                                  '\thelp\n'
                                  '\t  Arm the measured reset only after BOTH read-only hosts have '
                                  'shut down.\n'
                                  '\n'
                                  'config POWER_RESET_HISI\n')],
 'drivers/power/reset/Makefile': [('obj-$(CONFIG_POWER_RESET_HISI)',
                                   'obj-$(CONFIG_POWER_RESET_TY1208Z_MV100_SYSTEM) += '
                                   'ty1208z-mv100-system-restart.o\n'
                                   'obj-$(CONFIG_POWER_RESET_HISI)')],
 'drivers/clk/hisilicon/clk-ty1208z-ethernet.c': [('\t      '
                                                   'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")))',
                                                   '\t      '
                                                   'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")) '
                                                   '&&\n'
                                                   '\t    '
                                                   '!(IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM) '
                                                   '&&\n'
                                                   '\t      '
                                                   'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-system-ram")))')],
 'drivers/mmc/host/dw_mmc-hi3798mv100-ident.c': [('\t      '
                                                  'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")))',
                                                  '\t      '
                                                  'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")) '
                                                  '&&\n'
                                                  '\t    '
                                                  '!(IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM) &&\n'
                                                  '\t      '
                                                  'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-system-ram")))')],
 'drivers/net/phy/festa-ty1208z.c': [('\t      '
                                      'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")))',
                                      '\t      '
                                      'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")) '
                                      '&&\n'
                                      '\t    !(IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM) &&\n'
                                      '\t      '
                                      'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-system-ram")))')],
 'drivers/net/ethernet/hisilicon/hisi_femac.c': [('\t      '
                                                  'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")))',
                                                  '\t      '
                                                  'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")) '
                                                  '&&\n'
                                                  '\t    '
                                                  '!(IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM) &&\n'
                                                  '\t      '
                                                  'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-system-ram")))')],
 'drivers/mmc/host/dw_mmc-hi3798mv100-sd-ident.c': [('\t       '
                                                     'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-sdro-ram"))) '
                                                     ':',
                                                     '\t       '
                                                     'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-sdro-ram")) '
                                                     '||\n'
                                                     '\t      '
                                                     '(IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM) '
                                                     '&&\n'
                                                     '\t       '
                                                     'of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-system-ram"))) '
                                                     ':')],
 'drivers/clk/hisilicon/Kconfig': [('\tdepends on (!BLOCK && !MMC) || TY1208Z_ROUTER_SD_RO || '
                                    'TY1208Z_ROUTER_EMMC_RO\n',
                                    '\tdepends on (!BLOCK && !MMC) || TY1208Z_ROUTER_SD_RO || '
                                    'TY1208Z_ROUTER_EMMC_RO || TY1208Z_OPENWRT_SYSTEM\n')]}

TRANSFORMATIONS['drivers/clk/hisilicon/Kconfig'].append((
    '\tdepends on USB_OHCI_HCD_PLATFORM=y && !BLOCK && !MMC && !MTD\n'
    '\tdepends on !NET && !MODULES && !PM && !SMP && !DEBUG_FS\n',
    '\tdepends on USB_OHCI_HCD_PLATFORM=y && !MTD && !PM && !SMP && !DEBUG_FS\n'
    '\tdepends on (!BLOCK && !MMC && !NET && !MODULES) || TY1208Z_OPENWRT_SYSTEM\n'))
TRANSFORMATIONS['drivers/mmc/host/Kconfig'].append((
    '\tdepends on !SMP && !USB_SUPPORT && !MTD\n',
    '\tdepends on !SMP && !MTD\n'
    '\tdepends on !USB_SUPPORT || TY1208Z_OPENWRT_SYSTEM\n'))



def source_text(original, project, name):
    """Keep new board files authoritative when rebuilding an older native tree."""
    overlay = project / "overlay" / name
    return (overlay if overlay.is_file() else original / name).read_text()


def apply(text, name):
    for old, new in TRANSFORMATIONS.get(name, []):
        if text.count(old) != 1:
            raise ValueError("Native system anchor differs: " + name)
        text = text.replace(old, new)
    return text


def ensure(text, name):
    """Accept either the exact old baseline or the exact generated integration."""
    for old, new in TRANSFORMATIONS.get(name, []):
        if new in text:
            if text.count(new) != 1:
                raise ValueError("Duplicate native system change: " + name)
        elif text.count(old) == 1:
            text = text.replace(old, new)
        else:
            raise ValueError("Native system source differs: " + name)
    return text


def extend(changes):
    for name in TRANSFORMATIONS:
        if name not in changes:
            continue
        replacements = changes[name]
        if isinstance(replacements, tuple):
            replacements = [replacements]
        result = []
        for old, new in replacements:
            for before, after in TRANSFORMATIONS[name]:
                if before in new:
                    if new.count(before) != 1:
                        raise ValueError("Native system generator anchor differs: " + name)
                    new = new.replace(before, after)
            result.append((old, new))
        # block.c already has unrelated changes; append the stable disk-ID edit.
        if name == "drivers/mmc/core/block.c":
            result.extend(TRANSFORMATIONS[name])
        changes[name] = result
