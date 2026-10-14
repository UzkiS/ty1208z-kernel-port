#!/usr/bin/env python3
"""Build a copy of the exact native OpenWrt kernel; leave accepted trees intact."""
from native_system_patch import TRANSFORMATIONS, ensure
from prepare_openwrt import toolchain_from_native
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--taskbase', type=Path, required=True)
parser.add_argument('--native-source', type=Path)
parser.add_argument('--work', type=Path)
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
project = Path(__file__).resolve().parents[1]
base = args.taskbase.resolve()
lock = json.loads((project / 'openwrt/sources.lock.json').read_bytes())
source = args.native_source or base / 'router-emmc/build' / ('openwrt-ram-' + lock['openwrt']['commit'])
work = args.work or base / 'build/native-system-kernel'
state_path = work / 'kernel-build.json'
original = next((source / 'build_dir').glob('target-*/linux-hi3798mv100_apps/linux-6.12.112'))
state = {'status': 'starting-isolated-kernel', 'hardware_actions': False,
         'original_kernel': str(original), 'project': str(project)}


def save(status):
    state.update(status=status, updated_utc=datetime.now(timezone.utc).isoformat())
    state_path.write_text(json.dumps(state, indent=2) + '\n')
    print(status, flush=True)


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


kernel = work / 'linux-6.12.112'
if work.exists():
    assert args.resume, 'Explicit resume required for the inspected isolated build'
    assert kernel.is_dir()
else:
    work.mkdir(parents=True)
    save('copying-exact-native-kernel')
    shutil.copytree(original, kernel, symlinks=True)
for name in TRANSFORMATIONS:
    path = kernel / name
    expected = ensure((original / name).read_text(), name)
    if path.read_text() != expected:
        path.write_text(expected)
reset = Path('drivers/power/reset/ty1208z-mv100-system-restart.c')
if not (kernel / reset).exists() or (project / 'overlay' / reset).read_bytes() != (kernel / reset).read_bytes():
    shutil.copyfile(project / 'overlay' / reset, kernel / reset)

state['native_config_sha256'] = digest(original / '.config')


def options(text):
    values = {}
    for line in text.splitlines():
        match = re.fullmatch(r'(?:CONFIG_(\w+)=.*|# CONFIG_(\w+) is not set)', line)
        if match:
            values[match[1] or match[2]] = line
    return values


config = options((original / '.config').read_text())
config.update(options((project / 'openwrt/system/kernel.config').read_text()))
config['LOCALVERSION'] = 'CONFIG_LOCALVERSION="-ty1208z-openwrt-system"'
config['INITRAMFS_SOURCE'] = 'CONFIG_INITRAMFS_SOURCE=""'
existing = options((kernel / '.config').read_text())
if any(existing.get(name) != value for name, value in config.items()):
    (kernel / '.config').write_text('\n'.join(config.values()) + '\n')
toolchain, compiler_identity = toolchain_from_native(project, base)
compiler = toolchain / 'bin/arm-openwrt-linux-muslgnueabi-gcc'
cross = str(compiler).removesuffix('gcc')
state['compiler'] = compiler_identity
state['native_source'] = str(source)
state['openwrt_commit'] = lock['openwrt']['commit']
save('configuring-integrated-native-kernel')
make = ['make', '-C', str(kernel), 'ARCH=arm', 'CROSS_COMPILE=' + cross,
        'KERNELRELEASE=6.12.112', 'LOCALVERSION=']
environment = dict(os.environ, STAGING_DIR=str(next((source / 'staging_dir').glob('target-*'))),
                   SOURCE_DATE_EPOCH='1791676800', TZ='UTC', LC_ALL='C')
log = work / 'build.log'
with log.open('wb') as handle:
    result = subprocess.run(make + ['olddefconfig'], stdout=handle, stderr=subprocess.STDOUT, env=environment)
    if result.returncode:
        state['exit_code'] = result.returncode
        save('configuration-failed')
        raise SystemExit(result.returncode)
    resolved = (kernel / '.config').read_text()
    expected = options((project / 'openwrt/system/kernel.config').read_text())
    actual = options(resolved)
    assert all(actual.get(name) == value for name, value in expected.items()), 'System kernel fragment did not resolve'
    state['config_sha256'] = digest(kernel / '.config')
    save('building-integrated-native-kernel-and-modules')
    result = subprocess.run(make + ['-j4', 'zImage', 'modules'], stdout=handle, stderr=subprocess.STDOUT, env=environment)
state['exit_code'] = result.returncode
if result.returncode:
    save('kernel-build-failed')
    raise SystemExit(result.returncode)
subprocess.run([sys.executable, project / 'tools/inspect_kernel_layout.py', '--build', kernel,
                '--output', work / 'kernel-layout.json'], check=True)
layout = json.loads((work / 'kernel-layout.json').read_text())
assert layout['physical_bss_end'] < 0x1000000, 'Integrated kernel exceeds the measured low reservation'
state['layout'] = layout
state['zimage_sha256'] = digest(kernel / 'arch/arm/boot/zImage')
state['modules'] = len(list(kernel.rglob('*.ko')))
state['runtime_accepted'] = False
save('integrated-native-kernel-built-not-booted')
