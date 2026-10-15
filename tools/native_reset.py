#!/usr/bin/env python3
"""Package board configuration defaults and an ext4-safe reset backend."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / 'openwrt/system/reset'
FILES = {
    'sbin/ty1208z-reset': 'ty1208z-reset',
    'lib/preinit/81-ty1208z-reset': '81-ty1208z-reset',
    'www/luci-static/resources/view/system/reset.js': 'reset.js',
    'usr/share/luci/menu.d/ty1208z-reset.json': 'menu.json',
    'usr/share/rpcd/acl.d/ty1208z-reset.json': 'acl.json',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity():
    return {path.relative_to(PROJECT).as_posix(): digest(path)
            for path in [*sorted(SOURCE.iterdir()), Path(__file__)] if path.is_file()}


def install(apk, root, packages):
    subprocess.run([str(apk), 'add', '--root', str(root), '--usermode',
                    '--arch', 'arm_cortex-a7_neon-vfpv4', '--allow-untrusted', '--no-network',
                    '--no-scripts', '--no-commit-hooks', '--repositories-file', '/dev/null',
                    *map(str, packages)], check=True,
                   env=dict(os.environ, SOURCE_DATE_EPOCH='1791676800'))


def adapt_fstools(apk, original, output):
    """Keep APK ownership and the upstream mount_root; adapt only factoryreset."""
    output.mkdir(parents=True)
    meta = json.loads(subprocess.check_output([apk, 'adbdump', '--format', 'json', original]))
    assert meta['info']['name'] == 'fstools'
    assert meta['info']['version'] == '2026.05.23~16718b6e-r1'
    assert not meta.get('triggers'), 'Review changed fstools triggers'
    assert set(meta.get('scripts', {})) == {'post-install', 'pre-deinstall', 'post-upgrade'}
    files = output / 'files'
    files.mkdir()
    subprocess.run([apk, 'extract', '--allow-untrusted', '--no-chown',
                    '--destination', files, original], check=True)
    reset = files / 'sbin/factoryreset'
    assert digest(reset) == '6282e419b79c21d407e8b092ef4b49639d4ad778108fb070cf5d98c4bbbd6c3c', 'Upstream factoryreset drift'
    reset.write_bytes((SOURCE / 'factoryreset').read_bytes())
    reset.chmod(0o755)
    version = '2026.05.23~16718b6e-r2'
    package = output / ('fstools-' + version + '.apk')
    command = [apk, 'mkpkg', '--files', files, '--output', package]
    for key, value in meta['info'].items():
        if key in ('hashes', 'installed-size'):
            continue
        if key == 'version':
            value = version
        if isinstance(value, list):
            value = ' '.join(value)
        command += ['--info', key + ':' + str(value)]
    for kind, script in meta['scripts'].items():
        path = output / kind
        path.write_text(script)
        command += ['--script', kind + ':' + str(path)]
    subprocess.run(command, check=True)
    return package


def make_package(compiler, apk, version, root, output):
    output.mkdir(parents=True)
    files = output / 'files'
    files.mkdir()
    for name, source in FILES.items():
        target = files / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SOURCE / source).read_bytes())
        target.chmod(0o644 if target.suffix in ('.json', '.js') else 0o755)
    target = files / 'usr/libexec/ty1208z-reset-exchange'
    target.parent.mkdir(parents=True)
    subprocess.run([compiler, '-static', '-s', '-Os', '-Wall', '-Wextra', '-Werror',
                    SOURCE / 'reset-exchange.c', '-o', target], check=True,
                   env=dict(os.environ, STAGING_DIR=str(compiler.parent.parent.parent)))
    defaults = files / 'usr/share/ty1208z-reset'
    defaults.mkdir(parents=True)
    shutil.copytree(root / 'etc', defaults / 'etc', symlinks=True)
    # The first-install grow service remains owned/enabled, but is not a
    # user configuration and must not be requested again by factory reset.
    (defaults / 'etc/ty1208z-grow-p9').unlink(missing_ok=True)
    assert (defaults / 'etc/shadow').read_bytes().startswith(b'root::')
    for path in (defaults / 'etc/dropbear').glob('*'):
        assert not path.name.endswith('_host_key') and path.name != 'authorized_keys', 'Device credential in defaults'
    rows, links = [], []
    for path in sorted((defaults / 'etc').rglob('*')):
        name = path.relative_to(defaults).as_posix()
        assert not any(c.isspace() for c in name), 'Manifest paths must not contain whitespace'
        if path.is_symlink():
            link = os.readlink(path)
            assert not any(c.isspace() for c in link)
            links.append(name + ' ' + link + '\n')
        elif path.is_file():
            rows.append(digest(path) + '  ' + name + '\n')
        else:
            assert path.is_dir(), 'Unexpected default configuration object'
    (defaults / 'links.list').write_text(''.join(links))
    rows.append(digest(defaults / 'links.list') + '  links.list\n')
    (defaults / 'files.sha256').write_text(''.join(rows))
    identity = hashlib.sha256(json.dumps(source_identity(), sort_keys=True).encode() +
                              (defaults / 'files.sha256').read_bytes()).hexdigest()[:12]
    package = output / ('ty1208z-reset-1.0~' + identity + '-r1.apk')
    subprocess.run([apk, 'mkpkg', '--files', files, '--output', package,
                    '--info', 'name:ty1208z-reset', '--info', 'version:1.0~' + identity + '-r1',
                    '--info', 'arch:arm_cortex-a7_neon-vfpv4', '--info', 'license:GPL-2.0-only',
                    '--info', 'description:TY1208Z atomic ext4 configuration reset and LuCI',
                    '--info', 'depends:kernel=' + version + ' libc fstools luci-mod-system'], check=True,
                   env=dict(os.environ, SOURCE_DATE_EPOCH='1791676800'))
    return package
