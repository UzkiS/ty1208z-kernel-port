#!/usr/bin/env python3
"""Exercise reset transactions, crash recovery and credentials in an isolated tree."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

from native_reset import SOURCE, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    checked = []
    with tempfile.TemporaryDirectory(prefix='ty1208z-reset-') as directory:
        work = Path(directory)
        for name in ('bin', 'etc', 'root/.ssh', 'opt/docker', 'mnt/sdcard', 'proc/self',
                     'sys/class/block/mmcblk0p9', 'sys/class/net/eth0'):
            (work / name).mkdir(parents=True)
        shutil.copytree(root / 'usr/share/ty1208z-reset', work / 'defaults', symlinks=True)
        (work / 'proc/cmdline').write_text('root=/dev/mmcblk0p9\n')
        (work / 'proc/self/mountinfo').write_text('1 0 179:9 / / rw - ext4 /dev/root rw\n')
        for name, value in [('start', '1249280'), ('size', '14020608')]:
            (work / 'sys/class/block/mmcblk0p9' / name).write_text(value + '\n')
        (work / 'sys/class/net/eth0/address').write_text('02:11:22:33:44:50\n')
        for name in ('root/data', 'opt/docker/data', 'mnt/sdcard/data'):
            (work / name).write_text('kept\n')
        uci = work / 'bin/uci'
        uci.write_text('#!/bin/sh\nexec ' + shlex.join(['qemu-arm', '-L', str(root),
                       str(root / 'sbin/uci')]) + ' "$@"\n')
        uci.chmod(0o755)
        # Paths are redirected only in this test copy. Production has no root override.
        source = (SOURCE / 'ty1208z-reset').read_text()
        source = source.replace('defaults=/usr/share/ty1208z-reset', 'defaults=' + str(work / 'defaults'))
        source = source.replace('state=/.ty1208z-reset', 'state=' + str(work / '.ty1208z-reset'))
        source = source.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'PATH=' + shlex.quote(str(work / 'bin') + ':' + os.environ['PATH']))
        source = re.sub(r'(?<![\w$])/(?:etc|root|proc|sys)(?=[/\s\'])',
                        lambda m: str(work) + m[0], source)
        source = source.replace('/usr/libexec/ty1208z-reset-exchange', str(work / 'exchange'))
        source = source.replace('/sbin/reboot', 'false')
        # Host hexdump is optional; use the same 16 random bytes in an od shim.
        hexdump = work / 'bin/hexdump'
        hexdump.write_text('#!/bin/sh\nod -An -N16 -tx1 /dev/urandom | tr -d " \\n"\n')
        hexdump.chmod(0o755)
        script = work / 'reset'
        script.write_text(source)
        exchange = (SOURCE / 'reset-exchange.c').read_text().replace('geteuid() != 0', '0')
        exchange = exchange.replace('"/etc"', json.dumps(str(work / 'etc')))
        exchange = exchange.replace('"/.ty1208z-reset/etc"', json.dumps(str(work / '.ty1208z-reset/etc')))
        (work / 'exchange.c').write_text(exchange)
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-O2', str(work / 'exchange.c'),
                        '-o', str(work / 'exchange')], check=True)

        def run(*args, valid=True):
            result = subprocess.run(['sh', str(script), *args], capture_output=True, timeout=30)
            assert (result.returncode == 0) == valid, (args, result.stdout, result.stderr)
            return result

        def live():
            shutil.rmtree(work / 'etc')
            shutil.copytree(work / 'defaults/etc', work / 'etc', symlinks=True)
            (work / 'etc/shadow').write_text('root:OLD_PASSWORD:0:0:99999:7:::\n')
            (work / 'etc/custom-startup').write_text('removed\n')
            (work / 'etc/apk/world').write_text('kernel\nty1208z-reset\nuser-added-package\n')
            (work / 'etc/dropbear').mkdir(exist_ok=True)
            (work / 'etc/dropbear/authorized_keys').write_text('old-login-authorization\n')
            (work / 'etc/dropbear/dropbear_ed25519_host_key').write_text('device-host-identity\n')
            (work / 'root/.ssh/authorized_keys').write_text('old-root-authorization\n')

        def verify():
            assert (work / 'etc/shadow').read_bytes().startswith(b'root::')
            for name in ('etc/dropbear/authorized_keys', 'etc/custom-startup', 'root/.ssh/authorized_keys'):
                assert not (work / name).exists(), name
            assert (work / 'etc/dropbear/dropbear_ed25519_host_key').read_text() == 'device-host-identity\n'
            assert '02:11:22:33:44:50' in (work / 'etc/config/network').read_text()
            assert 'user-added-package' in (work / 'etc/apk/world').read_text()
            assert not (work / '.ty1208z-reset').exists()
            for name in ('root/data', 'opt/docker/data', 'mnt/sdcard/data'):
                assert (work / name).read_text() == 'kept\n'

        live()
        run('--check')
        run('-y')
        assert b'OLD_PASSWORD' in (work / 'etc/shadow').read_bytes(), 'live /etc changed before reboot'
        run('--check', valid=False)
        run('-y', valid=False)
        run('apply-boot')
        verify()
        checked.append('normal-reset-and-credential-removal-data-identity-preserved')
        # Power cut after the atomic exchange, before transaction cleanup.
        live()
        run('-y')
        subprocess.run([str(work / 'exchange')], check=True)
        run('apply-boot')
        verify()
        checked.append('post-exchange-crash-does-not-restore-old-password')
        # Power cut before the pending marker: discard only staging.
        live()
        (work / '.ty1208z-reset/etc').mkdir(parents=True)
        run('apply-boot')
        assert b'OLD_PASSWORD' in (work / 'etc/shadow').read_bytes()
        checked.append('incomplete-preparation-keeps-live-configuration')
        live()
        run('-y')
        (work / '.ty1208z-reset/etc/shadow').write_text('corrupted\n')
        run('apply-boot', valid=False)
        assert b'OLD_PASSWORD' in (work / 'etc/shadow').read_bytes()
        shutil.rmtree(work / '.ty1208z-reset')
        checked.append('corrupt-staging-refused-before-exchange')
        original = (work / 'defaults/etc/shadow').read_bytes()
        (work / 'defaults/etc/shadow').write_text('corrupted\n')
        run('-y', valid=False)
        assert not (work / '.ty1208z-reset').exists()
        (work / 'defaults/etc/shadow').write_bytes(original)
        checked.append('corrupt-defaults-refused-before-staging')
        link = work / 'defaults/etc/resolv.conf'
        target = link.readlink()
        link.unlink()
        link.symlink_to('/invalid-reset-default')
        run('-y', valid=False)
        link.unlink()
        link.symlink_to(target)
        live()
        run('-y')
        link = work / '.ty1208z-reset/etc/resolv.conf'
        link.unlink()
        link.symlink_to('/invalid-reset-staging')
        run('apply-boot', valid=False)
        assert b'OLD_PASSWORD' in (work / 'etc/shadow').read_bytes()
        shutil.rmtree(work / '.ty1208z-reset')
        checked.append('corrupt-default-and-staged-symlinks-refused')
        (work / '.ty1208z-reset').symlink_to(work / 'opt/docker', target_is_directory=True)
        run('apply-boot', valid=False)
        assert (work / 'opt/docker/data').read_text() == 'kept\n'
        (work / '.ty1208z-reset').unlink()
        (work / 'proc/self/mountinfo').write_text('1 0 179:9 / / rw - ext4 /dev/root rw\n2 1 1:1 / /etc rw - tmpfs tmpfs rw\n')
        run('-y', valid=False)
        checked.append('transaction-symlink-and-etc-submount-refused')
    print(json.dumps({'status': 'isolated host transactions with real ARM UCI passed; not hardware acceptance',
                      'checks': checked, 'backend_sha256': digest(SOURCE / 'ty1208z-reset')}, indent=2))


if __name__ == '__main__':
    main()
