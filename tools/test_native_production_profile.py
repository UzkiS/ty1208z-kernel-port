#!/usr/bin/env python3
"""Compile actual production DTs and check SMP, HIGHMEM and loader reservations."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from inspect_images import parse_fdt
from native_system_profile import native_system_profile, full_memory_reservations

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linuxsrc', type=Path, required=True)
    args = parser.parse_args()
    config = (args.linuxsrc / '.config').read_text()
    persistent = 'CONFIG_TY1208Z_EMMC_INSTALL_CANDIDATE=y\n' in config
    with tempfile.TemporaryDirectory(prefix='native-production-dt-') as directory:
        temp = Path(directory)
        for name in ('ram-rootfs.dts', 'persistent/disk-root.dts'):
            dts, dtb = temp / 'system.dts', temp / 'system.dtb'
            defines = (['-DTY1208Z_INITRD_START=0x04000000',
                        '-DTY1208Z_INITRD_END=0x05000000'] if name == 'ram-rootfs.dts' else [])
            subprocess.run(['cpp', '-nostdinc', '-undef', '-x', 'assembler-with-cpp',
                            '-I', str(ROOT / 'overlay/arch/arm/boot/dts/hisilicon'),
                            '-I', str(args.linuxsrc / 'include'),
                            *defines, str(ROOT / 'openwrt/system' / name), str(dts)], check=True)
            subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(dtb), str(dts)], check=True)
            blob = dtb.read_bytes()
            full_memory_reservations(blob)
            tree = parse_fdt(blob)
            if name == 'ram-rootfs.dts':
                assert native_system_profile(tree, config, allow_install_candidate=persistent)
                for before, after in (('CONFIG_SMP=y', '# CONFIG_SMP is not set'),
                                      ('CONFIG_HIGHMEM=y', '# CONFIG_HIGHMEM is not set'),
                                      ('CONFIG_NR_CPUS=4', 'CONFIG_NR_CPUS=1'),
                                      ('CONFIG_HI3798MV100_SD_WRITE=y', '# CONFIG_HI3798MV100_SD_WRITE is not set')):
                    try:
                        native_system_profile(tree, config.replace(before, after),
                                              allow_install_candidate=persistent)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Production profile accepted a regression: ' + before)
            else:
                chosen = next(n['properties'] for n in tree['nodes'] if n['path'] == '/chosen')
                assert 'linux,initrd-start' not in chosen
                assert 'root=/dev/mmcblk0p9' in chosen['bootargs']['strings'][0]
    print('NATIVE_PRODUCTION_PROFILE_PASS: compiled RAM/disk DTs, four cores, HIGHMEM, 1 GiB and precise reservations')


if __name__ == '__main__':
    main()
