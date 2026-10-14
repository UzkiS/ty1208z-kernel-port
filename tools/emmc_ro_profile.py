"""Exact low-256-MiB, user-area-only eMMC RAM read/restart profile."""
import re

from sd_audit_profile import BASE_PATHS

NODE = '/soc/mmc@f9830000'
RESTART = '/soc/emmc-ro-restart@f8a2c000'
IDENTITY = ['tianyi,ty1208z-ca-emmc-ro-ram', 'hi3798mv100-series']
BOOTARGS = ('console=ttyAMA0,115200 earlycon=pl011,mmio32,0xf8b00000 rdinit=/init '
            'loglevel=8 ignore_loglevel keep_bootcon panic=0 '
            'blkdevparts=mmcblk0:1M(boot)ro,1M(bootargs)ro,4M(baseparam)ro,4M(pqparam)ro,'
            '4M(logo)ro,20M(kernel)ro,64M(busybox)ro,512M(backup)ro,6846M(ubuntu)ro')
PROPERTIES = {'compatible': {'strings': ['tianyi,ty1208z-emmc-identification']},
              'reg': {'cells': [0xf9830000, 0x1000, 0xf8a220a0, 4]},
              'reg-names': {'strings': ['controller', 'crg40']},
              'interrupts': {'cells': [0, 35, 4]}, 'clock-frequency': {'cells': [100000000]},
              'fifo-depth': {'cells': [256]}, 'bus-width': {'cells': [1]},
              'max-frequency': {'cells': [25000000]}, 'non-removable': {}, 'no-sd': {}, 'no-sdio': {}}
RESTART_PROPERTIES = {'compatible': {'strings': ['tianyi,ty1208z-mv100-emmc-ro-restart']},
                      'reg': {'cells': [0xf8a2c000, 0x1000, 0xf8000ee0, 4, 0xf9830000, 0x1000, 0xf8a220a0, 4]}}
OPTIONS = {'MMC', 'MMC_DW', 'MMC_DW_PLTFM', 'MMC_DW_HI3798MV100_IDENT',
           'HI3798MV100_EMMC_READ_ONLY', 'BLOCK', 'MMC_BLOCK', 'POWER_RESET',
           'POWER_RESET_TY1208Z_MV100_EMMC_RO', 'EXT4_FS', 'PARTITION_ADVANCED', 'CMDLINE_PARTITION'}


def emmc_ro_profile(tree, config):
    if 'CONFIG_TY1208Z_ROUTER_EMMC_RO=y\n' in config:
        from native_emmc_profile import native_emmc_profile
        return native_emmc_profile(tree, config)
    props = {n['path']: n['properties'] for n in tree['nodes']}
    identity = props.get('/', {}).get('compatible', {}).get('strings', [])
    enabled = 'CONFIG_HI3798MV100_EMMC_READ_ONLY=y\n' in config
    if not enabled:
        if IDENTITY[0] in identity or RESTART in props or 'CONFIG_POWER_RESET_TY1208Z_MV100_EMMC_RO=y\n' in config:
            raise ValueError('eMMC RO board/restart outside explicit policy')
        return False
    if identity != IDENTITY or 'CONFIG_LOCALVERSION="-ty1208z-emmc-ro1"\n' not in config:
        raise ValueError('Unexpected eMMC RO board/release')
    if set(props) != BASE_PATHS | {NODE, RESTART}:
        raise ValueError('Unreviewed eMMC RO peripheral')
    if props['/memory@0'].get('reg', {}).get('cells') != [0, 0x10000000]:
        raise ValueError('Unexpected eMMC RO memory')
    if props['/chosen'].get('bootargs', {}).get('strings') != [BOOTARGS]:
        raise ValueError('eMMC RO RAM root or measured user-area partitions differ')
    for node, expected in ((NODE, PROPERTIES), (RESTART, RESTART_PROPERTIES)):
        if set(props[node]) != set(expected):
            raise ValueError('Unreviewed eMMC RO controller/reset properties')
        for name, value in expected.items():
            for kind, content in value.items():
                if props[node][name].get(kind) != content:
                    raise ValueError('eMMC RO resource/clock/bus differs')
    active = dict(re.findall(r'^CONFIG_(\w+)=([ym])$', config, re.MULTILINE))
    if any(active.get(name) != 'y' for name in OPTIONS) or 'CONFIG_MMC_BLOCK_MINORS=16\n' not in config:
        raise ValueError('Incomplete eMMC RO storage/read/reset configuration')
    restricted = {n for n in active if n.startswith(('MMC', 'POWER_RESET_', 'PWRSEQ_', 'BLK_DEV_'))}
    if restricted - OPTIONS - {'POWER_RESET_HISI', 'BLK_DEV_INITRD'}:
        raise ValueError('Unreviewed eMMC RO storage/reset driver')
    filesystems = {n for n in active if n.endswith('_FS')}
    if filesystems - {'PROC_FS', 'EXT4_FS'}:
        raise ValueError('Unreviewed eMMC RO filesystem')
    partitions = {n for n in active if n.endswith('_PARTITION')}
    if partitions - {'CMDLINE_PARTITION'}:
        raise ValueError('Unreviewed eMMC RO partition parser')
    forbidden = {'NET', 'MODULES', 'SMP', 'USB_SUPPORT', 'MTD', 'ATA', 'SCSI', 'PCI',
                 'WATCHDOG', 'DEBUG_FS', 'PM', 'HI3798MV100_EMMC_AUDIT', 'HI3798MV100_SD_AUDIT',
                 'HI3798MV100_EMMC_READ_SAMPLES', 'HI3798MV100_SD_READ_ONLY', 'BLK_DEV',
                 'TY1208Z_ETHERNET_INHERITED', 'FS_ENCRYPTION', 'FS_VERITY'}
    if set(active) & forbidden:
        raise ValueError('Prohibited subsystem in eMMC RO RAM profile')
    return True
