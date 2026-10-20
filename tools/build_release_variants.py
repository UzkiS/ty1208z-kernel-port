#!/usr/bin/env python3
"""Build all three offline network variants, sharing one compiled kernel/runtime."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import re

from native_network import PROFILES, MARKER
from package_release import archive_tree, checked, load, record, validate_deliveries, write_json

PROJECT = Path(__file__).resolve().parents[1]


def run(tool, *arguments):
    print('START', tool, flush=True)
    subprocess.run([sys.executable, PROJECT / 'tools' / tool, *map(str, arguments)], check=True)


def assemble(bootstrap, deliveries, version, output):
    # Build the shared RAM kit once. Its temporary DHCP uplink is independent
    # of the selected persistent first-install image.
    bridge_upgrade, bridge_first = deliveries['bridge']
    run('package_release.py', '--bootstrap', bootstrap, '--upgrade', bridge_upgrade,
        '--first-install', bridge_first, '--version', version, '--output', output)
    assets = output / 'assets'
    ram_tree = output / 'ram'
    summary = load(assets / 'release-manifest.json')
    installer_hash = record(ram_tree / load(bridge_first / 'manifest.json')['installer']['file'])
    profiles = {}
    (ram_tree / 'first-install-manifest.json').unlink()
    for name in PROFILES:
        upgrade_path, first_path = deliveries[name]
        _, upgrade, first, _, _ = validate_deliveries(bootstrap, upgrade_path, first_path)
        if upgrade.get('network_profile') != name or first.get('network_profile') != name:
            raise ValueError('Delivery profile differs: ' + name)
        if record(first_path / first['installer']['file']) != installer_hash:
            raise ValueError('Variants require the same temporary first-install backend')
        for root in (upgrade_path / 'root', first_path / 'root'):
            if load(root / MARKER)['profile'] != name:
                raise ValueError('Packaged root network identity differs: ' + name)
        images = {}
        for base, receipt, kind in ((upgrade_path, upgrade, 'sysupgrade'), (first_path, first, 'first-install')):
            filename = 'ty1208z-ca-' + name + '-' + kind + '-' + version + '.bin'
            shutil.copyfile(checked(base, receipt['image']['file'], receipt['image']), assets / filename)
            images[kind] = filename
        profiles[name] = {**load(upgrade_path / 'root' / MARKER), 'images': images,
                          'hardware_acceptance': 'Combined network profile not newly tested on the board'}
        write_json(ram_tree / ('first-install-manifests/' + name + '.json'), first)
    for kind in ('sysupgrade', 'first-install'):
        (assets / ('ty1208z-ca-' + kind + '-' + version + '.bin')).unlink()
    # Add current user-facing instructions to both the download set and RAM kit.
    readme = (PROJECT / 'docs/network-variants.md').read_text(encoding='utf-8')
    (assets / 'README.zh-CN.md').write_text(readme, encoding='utf-8')
    (ram_tree / 'NETWORK-VARIANTS.zh-CN.md').write_text(readme, encoding='utf-8')
    (ram_tree / 'RAM-SHA256SUMS.txt').unlink()
    (ram_tree / 'RAM-SHA256SUMS.txt').write_text(''.join(
        record(path)['sha256'] + '  ' + path.relative_to(ram_tree).as_posix() + '\n'
        for path in sorted(ram_tree.rglob('*')) if path.is_file()), encoding='utf-8')
    archive_tree(ram_tree, assets / ('ty1208z-ca-install-ram-' + version + '.tar.gz'))
    (assets / 'release-manifest.json').unlink()
    (assets / 'SHA256SUMS.txt').unlink()
    summary.update(schema=2, network_profiles=profiles,
                   shared_install_ram='Existing temporary DHCP uplink; supports all three persistent image profiles',
                   files={path.name: record(path) for path in sorted(assets.iterdir())})
    write_json(assets / 'release-manifest.json', summary)
    (assets / 'SHA256SUMS.txt').write_text(''.join(
        record(path)['sha256'] + '  ' + path.name + '\n'
        for path in sorted(assets.iterdir())), encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('taskbase', 'source', 'disk-root', 'bootstrap', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9][A-Za-z0-9._-]{0,63}', args.version):
        raise ValueError('Invalid release version')
    if args.output.exists():
        raise ValueError('Inspect completed/partial variant builds; use a new output directory')
    args.output.mkdir(parents=True)
    run('test_native_network.py', '--root', args.disk_root / 'root')
    deliveries = {}
    for name in PROFILES:
        variant = args.output / name
        upgrade, first = variant / 'upgrade', variant / 'first-install'
        run('prepare_native_upgrade.py', '--taskbase', args.taskbase, '--source', args.source,
            '--disk-root', args.disk_root, '--network-profile', name, '--output', upgrade)
        if name != 'bridge':
            run('test_native_network_fw4.py', '--root', upgrade / 'root')
        run('test_native_upgrade.py', '--delivery', upgrade)
        # test_native_upgrade already exercises this root's reset transactions.
        run('prepare_native_first_install.py', '--source', args.source, '--upgraded-root', upgrade / 'root',
            '--disk', args.disk_root, '--output', first)
        run('test_native_reset.py', '--root', first / 'root')
        deliveries[name] = upgrade, first
    summary = assemble(args.bootstrap, deliveries, args.version, args.output / 'release')
    # Record only public identities, never build host paths.
    write_json(args.output / 'manifest.json', summary)
    print(json.dumps({'status': 'three offline variants built; not published or hardware accepted',
                      'profiles': list(PROFILES), 'files': summary['files']}, indent=2))


if __name__ == '__main__':
    main()
