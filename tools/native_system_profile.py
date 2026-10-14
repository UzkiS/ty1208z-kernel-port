"""Measured native integration boundaries with reused userspace evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

from inspect_images import parse_fdt
from native_emmc_profile import BOOTARGS, NODE as EMMC_NODE, PROPERTIES as EMMC_PROPERTIES
from sd_ident_profile import NODE as SD_NODE, PROPERTIES as SD_PROPERTIES
from ram768_profile import memory_boot_evidence
from ethernet_net_profile import NETWORK_NODES
from usb_host_profile import HOST_NODES, USB_OPTIONS, validate_usb_resources

COMPATIBLE = 'tianyi,ty1208z-ca-openwrt-system-ram'
RESTART = '/soc/system-restart@f8a2c000'
BASE = {'/', '/aliases', '/chosen', '/memory@0', '/cpus', '/cpus/cpu@0',
        '/clock-24m', '/clock-83m3', '/interrupt-controller@f8a01000', '/soc',
        '/soc/timer@f8a29000', '/soc/serial@f8b00000'}


def native_system_profile(tree, config, *, allow_install_candidate=False):
    props = {n['path']: n['properties'] for n in tree['nodes']}
    if props['/'].get('compatible', {}).get('strings') != [COMPATIBLE, 'hi3798mv100-series']:
        return False
    required = {'TY1208Z_OPENWRT_SYSTEM', 'HI3798MV100_TIMER', 'ARCH_HI3798MV100',
                'HISI_FEMAC', 'MDIO_HISI_FEMAC', 'TY1208Z_ETHERNET_INHERITED', 'FESTA_TY1208Z_PHY',
                'HI3798MV100_EMMC_READ_ONLY', 'HI3798MV100_SD_READ_ONLY', 'CMDLINE_PARTITION',
                'MMC_DW_HI3798MV100_IDENT', 'MMC_DW_HI3798MV100_SD_IDENT', 'MMC_BLOCK',
                'POWER_RESET_TY1208Z_MV100_SYSTEM', 'PROC_PAGE_MONITOR', 'MEMCG', 'CGROUPS',
                'CFS_BANDWIDTH', 'SECCOMP', 'SECCOMP_FILTER', 'NAMESPACES', 'NET_NS', 'PID_NS',
                'OVERLAY_FS', 'TMPFS_XATTR', 'BLOCK', 'EXT4_FS', 'VFAT_FS', 'EXFAT_FS',
                'ARM_APPENDED_DTB', 'BLK_DEV_INITRD', 'RD_GZIP', 'MODULES',
                'TY1208Z_USB_HOST0_EXPERIMENT', 'CFG80211', 'FW_LOADER', 'CRYPTO_MD5'} | USB_OPTIONS
    forbidden = {'USB_STORAGE', 'USB_UAS', 'SMP', 'HIGHMEM', 'WATCHDOG', 'DEBUG_FS', 'PM', 'MTD', 'MMC_TEST',
                 'TY1208Z_EMMC_INSTALL_CANDIDATE',
                 'OF_PARTITION', 'BLK_DEV_WRITE_MOUNTED', 'TY1208Z_ROUTER_RAM768',
                 'TY1208Z_ROUTER_SD_RO', 'TY1208Z_ROUTER_EMMC_RO', 'POWER_RESET_TY1208Z_MV100_EMMC_RO',
                 'POWER_RESET_TY1208Z_MV100_SD', 'POWER_RESET_TY1208Z_SP805',
                 'ARM_ATAG_DTB_COMPAT', 'INITRAMFS_FORCE', 'CMDLINE_FORCE'}
    active = dict(re.findall(r'^CONFIG_(\w+)=([ym])$', config, re.MULTILINE))
    if allow_install_candidate:
        if active.get('TY1208Z_EMMC_INSTALL_CANDIDATE') != 'y':
            raise ValueError('Explicit installation mode requires its exact opt-in kernel')
        forbidden.remove('TY1208Z_EMMC_INSTALL_CANDIDATE')
        forbidden.remove('USB_STORAGE')
        if 'USB_STORAGE' in active:
            required.update({'SCSI', 'BLK_DEV_SD', 'USB_STORAGE'})
    if not all(active.get(n) == 'y' for n in required) or active.keys() & forbidden:
        raise ValueError('Integrated native configuration differs from the measured composition')
    if ('CONFIG_LOCALVERSION="-ty1208z-openwrt-system"\n' not in config or
            'CONFIG_INITRAMFS_SOURCE=""\n' not in config or
            set(props) != BASE | NETWORK_NODES | HOST_NODES | {EMMC_NODE, SD_NODE, RESTART} or
            props['/memory@0']['reg'].get('cells') != [0, 0x30000000] or
            props['/chosen']['bootargs'].get('strings') != [BOOTARGS]):
        raise ValueError('Integrated identity/memory/peripherals/partitions differ')
    validate_usb_resources(props)
    for node, expected in ((EMMC_NODE, EMMC_PROPERTIES), (SD_NODE, SD_PROPERTIES)):
        if set(props[node]) != set(expected) or any(props[node][name].get(kind) != value
                for name, kinds in expected.items() for kind, value in kinds.items()):
            raise ValueError('Integrated storage resources differ: ' + node)
    reset = props[RESTART]
    if (set(reset) != {'compatible', 'reg'} or
            reset['compatible'].get('strings') != ['tianyi,ty1208z-mv100-system-restart'] or
            reset['reg'].get('cells') != [0xf8a2c000, 0x1000, 0xf8000ee0, 4,
                                         0xf9830000, 0x1000, 0xf9820000, 0x1000,
                                         0xf9890000, 0x10000, 0xf9880000, 0x10000,
                                         0xf8a220b8, 4, 0xf8a220bc, 4]):
        raise ValueError('Integrated storage/USB reset resources differ')
    aliases = props['/aliases']
    if aliases.get('mmc0', {}).get('strings') != [EMMC_NODE] or aliases.get('mmc1', {}).get('strings') != [SD_NODE]:
        raise ValueError('Stable read-only disk host aliases differ')
    return True


def prepare_native_system(artifacts, metadata, allocation_evidence, *, allow_install_candidate=False):
    artifacts = Path(artifacts)
    manifest = json.loads((artifacts / 'manifest.json').read_bytes())
    if bool(manifest.get('persistent_candidate')) != allow_install_candidate:
        raise ValueError('Installation candidate requires an explicit authorized boot mode')
    if (manifest['board'] != COMPATIBLE or manifest['persistent_writes'] is not False or
            manifest['memory_end'] != 0x30000000 or allocation_evidence is None):
        raise ValueError('Native system lacks its fresh allocation evidence or exact manifest')
    allocation_hash = memory_boot_evidence(allocation_evidence, metadata)
    for name, expected in manifest['files'].items():
        path = artifacts / name
        if not path.resolve().is_relative_to(artifacts.resolve()):
            raise ValueError('Native system manifest path escapes artifacts')
        with path.open('rb') as stream:
            actual = {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
        if actual != expected:
            raise ValueError('Native system delivery changed: ' + name)
    tree = parse_fdt((artifacts / 'ty1208z-diagnostic.dtb').read_bytes())
    if not native_system_profile(tree, (artifacts / 'linux.config').read_text(),
                                 allow_install_candidate=allow_install_candidate):
        raise ValueError('Native system board profile differs')
    dtb = (artifacts / 'ty1208z-diagnostic.dtb').read_bytes()
    offset = struct.unpack_from('>I', dtb, 16)[0]
    if struct.unpack_from('>QQQQ', dtb, offset) != (0, 0x1000000, 0, 0):
        raise ValueError('Native system lacks the exact low reservation')
    layout = json.loads((artifacts / 'checks/kernel-layout.json').read_bytes())
    if not 0x8000 == layout['physical_start'] < layout['physical_image_end'] <= layout['physical_bss_end'] < 0x1000000:
        raise ValueError('Native system kernel footprint crosses the measured reservation')
    image = (artifacts / 'uImage-UNTESTED.bin').read_bytes()
    zimage = (artifacts / 'zImage').read_bytes()
    if image[64:] != zimage + dtb or layout['zimage_sha256'] != hashlib.sha256(zimage).hexdigest():
        raise ValueError('Native system image/kernel layout differs')
    initrd = (artifacts / 'rootfs.cpio.gz').read_bytes()
    if not 0 < len(initrd) <= 512 * 65535 - 1:
        raise ValueError('Native bootstrap exceeds the accepted transfer budget')
    with gzip.GzipFile(fileobj=__import__('io').BytesIO(initrd)) as stream:
        unpacked = stream.read(96 * 1024 * 1024 + 1)
    if len(unpacked) > 96 * 1024 * 1024 or not unpacked.startswith(b'070701'):
        raise ValueError('Native bootstrap expansion is unbounded')
    props = {n['path']: n['properties'] for n in tree['nodes']}
    end = 0x4000000 + len(initrd)
    if (props['/chosen']['linux,initrd-start'].get('cells') != [0x4000000] or
            props['/chosen']['linux,initrd-end'].get('cells') != [end] or end >= 0x8e62000):
        raise ValueError('Native bootstrap DT range differs')
    return {'schema': 1, 'status': 'validated native RAM placement; hardware untested',
            'installation_candidate': allow_install_candidate,
            'storage_write_capable': allow_install_candidate,
            'card_cache_control_allowed': allow_install_candidate,
            'image_bytes': len(image), 'image_sha256': hashlib.sha256(image).hexdigest(),
            'image_crc32': f'{zlib.crc32(image):08x}', 'header_address': 0x1ffffc0,
            'load_address': 0x2000000, 'entry_address': 0x2000000, 'kernel_layout': layout,
            'inspection_raw_sha256': metadata['raw_sha256'], 'memory_end': 0x30000000,
            'allocation_evidence_sha256': allocation_hash, 'load_command': 'loady 1ffffc0 115200',
            'crc_command': f'crc32 1ffffc0 {len(image):x}', 'boot_command': 'bootm 1ffffc0',
            'persistent_writes': False,
            'additional_loads': [{'file': 'rootfs.cpio.gz', 'address': 0x4000000,
                                  'bytes': len(initrd), 'sha256': hashlib.sha256(initrd).hexdigest(),
                                  'uncompressed_bytes': len(unpacked),
                                  'load_command': 'loady 4000000 115200',
                                  'crc_command': f'crc32 4000000 {len(initrd):x}',
                                  'image_crc32': f'{zlib.crc32(initrd):08x}'}]}
