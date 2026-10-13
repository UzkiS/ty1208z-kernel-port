#!/usr/bin/env python3
"""Exact RO board/partition/reset gates, with actual built RAM placement."""
import argparse
import copy
from pathlib import Path
import unittest

from emmc_ro_profile import emmc_ro_profile, BASE_PATHS, NODE, RESTART, IDENTITY, BOOTARGS, OPTIONS, PROPERTIES, RESTART_PROPERTIES
from test_sd_ident_profile import check_built as check_ident_built


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tree = {'nodes': [{'path': path, 'properties': {}} for path in sorted(BASE_PATHS | {NODE, RESTART})]}
        props = {n['path']: n['properties'] for n in self.tree['nodes']}
        props['/']['compatible'] = {'strings': IDENTITY.copy()}
        props['/memory@0']['reg'] = {'cells': [0, 0x10000000]}
        props['/chosen']['bootargs'] = {'strings': [BOOTARGS]}
        props[NODE].update(copy.deepcopy(PROPERTIES))
        props[RESTART].update(copy.deepcopy(RESTART_PROPERTIES))
        self.config = 'CONFIG_LOCALVERSION="-ty1208z-emmc-ro1"\nCONFIG_MMC_BLOCK_MINORS=16\n'
        self.config += ''.join(f'CONFIG_{name}=y\n' for name in sorted(OPTIONS))

    def test_config_guards(self):
        self.assertTrue(emmc_ro_profile(self.tree, self.config))
        for name in OPTIONS:
            with self.subTest(missing=name), self.assertRaises(ValueError):
                emmc_ro_profile(self.tree, self.config.replace(f'CONFIG_{name}=y\n', ''))
        for name in ('NET', 'MODULES', 'USB_SUPPORT', 'SMP', 'PM', 'MMC_TEST', 'PWRSEQ_EMMC',
                     'MMC_DW_HI3798MV100_SD_IDENT', 'HI3798MV100_EMMC_READ_SAMPLES', 'MSDOS_PARTITION',
                     'EFI_PARTITION', 'BTRFS_FS', 'VFAT_FS', 'FS_ENCRYPTION', 'FS_VERITY', 'BLK_DEV_LOOP',
                     'POWER_RESET_TY1208Z_SP805', 'TY1208Z_ETHERNET_INHERITED'):
            with self.subTest(enabled=name), self.assertRaises(ValueError):
                emmc_ro_profile(self.tree, self.config + f'CONFIG_{name}=y\n')
        for old, new in (('MINORS=16', 'MINORS=8'), ('emmc-ro1', 'emmc-read1')):
            with self.assertRaises(ValueError):
                emmc_ro_profile(self.tree, self.config.replace(old, new))

    def test_exact_resources(self):
        for path, expected in ((NODE, PROPERTIES), (RESTART, RESTART_PROPERTIES)):
            for name, value in expected.items():
                changed = copy.deepcopy(self.tree)
                props = next(n['properties'] for n in changed['nodes'] if n['path'] == path)
                del props[name]
                with self.subTest(path=path, missing=name), self.assertRaises(ValueError):
                    emmc_ro_profile(changed, self.config)
                for kind, content in value.items():
                    changed = copy.deepcopy(self.tree)
                    props = next(n['properties'] for n in changed['nodes'] if n['path'] == path)
                    props[name][kind][0] = content[0] + 1 if isinstance(content[0], int) else 'foreign'
                    with self.subTest(path=path, changed=name), self.assertRaises(ValueError):
                        emmc_ro_profile(changed, self.config)
        for path, name, value in (('/', 'compatible', {'strings': ['foreign']}),
                                  ('/memory@0', 'reg', {'cells': [0, 0x30000000]}),
                                  ('/chosen', 'bootargs', {'strings': [BOOTARGS.replace('ro,', ',', 1)]})):
            changed = copy.deepcopy(self.tree)
            next(n['properties'] for n in changed['nodes'] if n['path'] == path)[name] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                emmc_ro_profile(changed, self.config)
        changed = copy.deepcopy(self.tree)
        changed['nodes'].append({'path': '/soc/foreign', 'properties': {}})
        with self.assertRaises(ValueError):
            emmc_ro_profile(changed, self.config)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path)
    args = parser.parse_args()
    if args.artifacts:
        check_ident_built(args.artifacts, emmc_ro_profile)
        print('EMMC_RO_RAM_PLAN_PASS exact user-area/partition/filesystem/reset and low256 placement')
    unittest.main(argv=[__file__], verbosity=2)
