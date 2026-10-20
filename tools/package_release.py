#!/usr/bin/env python3
"""Verify matching build deliveries and assemble public GitHub Release assets offline."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import zlib
from prepare_native_userspace import native_archive

ROOT = Path(__file__).resolve().parents[1]
EPOCH = 1791676800


def record(path):
    with path.open('rb') as stream:
        return {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}


def load(path):
    return json.loads(path.read_bytes())


def checked(base, name, expected):
    path = base / name
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
        raise ValueError('Delivery path escapes its directory: ' + name)
    actual = record(path)
    if any(actual[key] != value for key, value in expected.items() if key in actual):
        raise ValueError('Delivery checksum/size differs: ' + name)
    if 'sha256' not in expected:
        raise ValueError('Delivery lacks a checksum: ' + name)
    return path


def public_metadata(value):
    """Build host paths are unnecessary in published provenance; retain filenames."""
    if isinstance(value, dict):
        return {key: public_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_metadata(item) for item in value]
    if isinstance(value, str) and re.match(r'^(?:/(?:home|mnt|Users)/|[A-Za-z]:[\\/]|\\\\)', value):
        return value.replace('\\', '/').rsplit('/', 1)[-1]
    return value


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(public_metadata(data), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def check_runtime_content(name, payload):
    prefixes = (str(Path.home()).encode() + b'/', str(Path.home()).encode() + b'\\')
    if any(prefix in payload for prefix in prefixes):
        raise ValueError('Build account path remains in runtime content: ' + name)
    if name == 'etc/shadow' and not payload.startswith(b'root::'):
        raise ValueError('Release root password differs from the empty default')
    if name.startswith('etc/dropbear/') and (name.endswith('_host_key') or name.endswith('authorized_keys')):
        raise ValueError('Device SSH identity in release content: ' + name)


def archive_tree(tree, output):
    with output.open('wb') as target:
        with gzip.GzipFile(filename='', fileobj=target, mode='wb', compresslevel=1, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.USTAR_FORMAT) as archive:
                for path in sorted(tree.rglob('*')):
                    if path.is_dir() and not path.is_symlink():
                        continue
                    if not path.is_file() or path.is_symlink():
                        raise ValueError('Unexpected RAM delivery entry: ' + str(path))
                    member = tarfile.TarInfo(path.relative_to(tree).as_posix())
                    member.size, member.mode, member.mtime = path.stat().st_size, 0o644, EPOCH
                    with path.open('rb') as stream:
                        archive.addfile(member, stream)


def validate_deliveries(bootstrap, upgrade_path, first_install):
    """Validate every variant with the same runtime, kernel and privacy checks."""
    ram, upgrade, first = [load(path / 'manifest.json') for path in
                           (bootstrap, upgrade_path, first_install)]
    abi = upgrade['manifest']['kernel_abi']
    for key in ('kernel_abi', 'kernel_bytes', 'kernel_sha256', 'board', 'layout'):
        if first['manifest'][key] != upgrade['manifest'][key]:
            raise ValueError('First-install/sysupgrade mismatch: ' + key)
    if not ram['persistent_candidate'] or ram['memory_end'] != 0x40000000:
        raise ValueError('Release requires the full-memory installation RAM profile')
    for name, expected in ram['files'].items():
        checked(bootstrap, name, expected)
    for name, (_, _, payload) in native_archive(bootstrap, 'rootfs.cpio.gz').items():
        check_runtime_content(name, payload)
    with tarfile.open(bootstrap / ram['supplement']) as packed:
        for member in packed:
            if member.isfile():
                check_runtime_content(member.name, packed.extractfile(member).read())
    for base in (upgrade_path, first_install):
        for path in (base / 'root').rglob('*'):
            if path.is_file() and not path.is_symlink():
                check_runtime_content(path.relative_to(base / 'root').as_posix(), path.read_bytes())
    ram_kernel = (bootstrap / 'zImage').read_bytes()
    for base, receipt in ((upgrade_path, upgrade), (first_install, first)):
        image = checked(base, receipt['image']['file'], receipt['image'])
        with tarfile.open(image) as packed:
            kernel = packed.extractfile('kernel').read()
            if kernel[64:64 + len(ram_kernel)] != ram_kernel:
                raise ValueError('RAM and disk kernels differ')
            if hashlib.sha256(kernel).hexdigest() != receipt['manifest']['kernel_sha256']:
                raise ValueError('Packaged disk kernel checksum differs')
    ramdb = (upgrade_path / 'root/lib/apk/db/installed').read_text()
    if 'P:kernel\nV:' + abi + '\n' not in ramdb:
        raise ValueError('Packaged kernel ABI absent from the installed APK database')
    module = upgrade_path / 'root/lib/modules/6.12.112/rdawfmac.ko'
    module_name = 'lib/modules/6.12.112/rdawfmac.ko'
    module_identity = ram['supplement_files'][module_name]
    checked(module.parent, module.name, module_identity)
    if b'/home/' in module.read_bytes() or b'\\Users\\' in module.read_bytes():
        raise ValueError('Packaged RDA module contains a build host path; use the Kbuild prefix map')
    checked(first_install / 'root', module_name, module_identity)
    with tarfile.open(bootstrap / ram['supplement']) as packed:
        data = packed.extractfile(module_name).read()
        if hashlib.sha256(data).hexdigest() != module_identity['sha256']:
            raise ValueError('RAM/disk packaged RDA modules differ')
        database = packed.extractfile('lib/apk/db/installed').read().decode()
        if 'P:kernel\nV:' + abi + '\n' not in database:
            raise ValueError('RAM/disk kernel APK ABIs differ')
    return ram, upgrade, first, abi, module_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap', type=Path, required=True)
    parser.add_argument('--upgrade', type=Path, required=True)
    parser.add_argument('--first-install', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9][A-Za-z0-9._-]{0,63}', args.version):
        raise ValueError('Invalid release version')
    if args.output.exists():
        raise ValueError('Inspect the existing release directory before replacing it')
    ram, upgrade, first, abi, module_identity = validate_deliveries(args.bootstrap, args.upgrade, args.first_install)
    args.output.mkdir(parents=True)
    assets = args.output / 'assets'
    assets.mkdir()
    ram_tree = args.output / 'ram'
    ram_tree.mkdir()
    for name in ram['files']:
        target = ram_tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith('.json'):
            write_json(target, load(args.bootstrap / name))
        else:
            shutil.copyfile(args.bootstrap / name, target)
    if 'private_rda_firmware' in ram:
        ram['rda_firmware'] = ram.pop('private_rda_firmware')
    ram['files'] = {name: record(ram_tree / name) for name in ram['files']}
    ram['kernel_abi'] = abi
    # The build receipt is immutable evidence of compilation, not a hardware claim.
    write_json(ram_tree / 'manifest.json', ram)
    installer = checked(args.first_install, first['installer']['file'], first['installer'])
    shutil.copyfile(installer, ram_tree / installer.name)
    write_json(ram_tree / 'first-install-manifest.json', first)
    readme = (ROOT / 'docs/install-ram-bundle.md').read_text(encoding='utf-8')
    replacements = {'KERNEL_ABI': abi, 'INSTALLER_FILE': installer.name,
                    'INSTALLER_SHA256': record(installer)['sha256'],
                    'SUPPLEMENT_SHA256': record(ram_tree / ram['supplement'])['sha256']}
    for kind, name in (('UIMAGE', 'uImage-UNTESTED.bin'), ('INITRD', 'rootfs.cpio.gz')):
        data = (ram_tree / name).read_bytes()
        replacements.update({kind + '_BYTES': str(len(data)), kind + '_HEX_BYTES': f'{len(data):x}',
                             kind + '_CRC32': f'{zlib.crc32(data):08x}'})
    for name, value in replacements.items():
        readme = readme.replace('@' + name + '@', value)
    if re.search(r'@[A-Z_]+@', readme):
        raise ValueError('Unfilled RAM README placeholder')
    (ram_tree / 'README.zh-CN.md').write_text(readme, encoding='utf-8')
    (ram_tree / 'RAM-SHA256SUMS.txt').write_text(''.join(record(p)['sha256'] + '  ' + p.relative_to(ram_tree).as_posix() + '\n'
                                                      for p in sorted(ram_tree.rglob('*')) if p.is_file()), encoding='utf-8')
    for base, receipt, kind in ((args.upgrade, upgrade, 'sysupgrade'),
                                (args.first_install, first, 'first-install')):
        name = 'ty1208z-ca-' + kind + '-' + args.version + '.bin'
        shutil.copyfile(base / receipt['image']['file'], assets / name)
    archive_tree(ram_tree, assets / ('ty1208z-ca-install-ram-' + args.version + '.tar.gz'))
    archive_tree(ROOT / 'firmware/rda5995', assets / ('ty1208z-ca-rda5995-firmware-' + args.version + '.tar.gz'))
    summary = {'schema': 1, 'version': args.version, 'board': 'tianyi,ty1208z-ca', 'kernel_abi': abi,
               'zimage_sha256': ram['files']['zImage']['sha256'],
               'rda_module_sha256': module_identity['sha256'],
               'rda_build_module_sha256': ram['rda_module']['sha256'],
               'files': {path.name: record(path) for path in sorted(assets.iterdir())},
               'first_install_acceptance': 'Reuses the accepted installer; this image has not repeated the full 1 GiB write.',
               'sources': 'https://github.com/UzkiS/ty1208z-kernel-port',
               'firmware': 'Included matching RDA5995 runtime files; upstream HEX references remain in wifi/vendor/.'}
    write_json(assets / 'release-manifest.json', summary)
    (assets / 'SHA256SUMS.txt').write_text(''.join(record(p)['sha256'] + '  ' + p.name + '\n'
                                               for p in sorted(assets.iterdir())), encoding='utf-8')
    print(json.dumps({'status': 'release assets verified and assembled; nothing uploaded', **summary}, indent=2))


if __name__ == '__main__':
    main()
