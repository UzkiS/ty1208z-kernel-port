#!/usr/bin/env python3
"""Package the built native system for bounded RAM boot and network supplementation."""
from prepare_native_userspace import native_archive, record
from native_system_patch import TRANSFORMATIONS, ensure
from prepare_openwrt import toolchain_from_native
from prepare_native_userspace import prepare
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--taskbase', type=Path, required=True)
parser.add_argument('--kernel-build', type=Path)
parser.add_argument('--base-artifacts', type=Path)
parser.add_argument('--combined-artifacts', type=Path)
parser.add_argument('--work', type=Path)
parser.add_argument('--output', type=Path)
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
project = Path(__file__).resolve().parents[1]
base = args.taskbase.resolve()
build = args.kernel_build or base / 'build/native-system-kernel'
kernel = build / 'linux-6.12.112'
work = args.work or base / 'build/native-system-package'
output = args.output or project / 'artifacts/openwrt-system-ram'
state = json.loads((build / 'kernel-build.json').read_bytes())
source = Path(state['native_source'])
base_artifacts = args.base_artifacts or project / 'artifacts/openwrt-router-emmcro'
combined = args.combined_artifacts or project / 'artifacts/openwrt-container-applications-qemu'
if output.exists() or work.exists():
    assert args.resume and not (output / 'manifest.json').exists(), 'Inspect an existing completed package rather than overwrite'
work.mkdir(parents=True, exist_ok=True)
output.mkdir(parents=True, exist_ok=True)
original_kernel = next((source / 'build_dir').glob('target-*/linux-hi3798mv100_apps/linux-6.12.112'))
for name in TRANSFORMATIONS:
    assert (kernel / name).read_text() == ensure((original_kernel / name).read_text(), name), name
assert state['status'] == 'integrated-native-kernel-built-not-booted' and state['exit_code'] == 0

root = work / 'root'
if root.exists():
    assert not root.is_symlink() and root.resolve().is_relative_to(work.resolve())
    shutil.rmtree(root)
root.mkdir()
entries = native_archive(base_artifacts, 'rootfs.cpio.gz')
for name, (mode, links, data) in entries.items():
    if name.startswith('lib/modules/') or name == 'lib/modules' or name == 'usr/bin/xray':
        continue
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if stat.S_ISDIR(mode):
        p.mkdir(exist_ok=True)
    elif stat.S_ISLNK(mode):
        if p.is_symlink():
            assert p.readlink().as_posix() == data.decode(), name
        else:
            p.symlink_to(data.decode())
    elif stat.S_ISREG(mode):
        assert links == 1, name
        p.write_bytes(data)
        p.chmod(stat.S_IMODE(mode))

toolchain, _ = toolchain_from_native(project, base)
compiler = toolchain / 'bin/arm-openwrt-linux-muslgnueabi-gcc'
with (work / 'modules-install.log').open('wb') as log:
    subprocess.run(['make', '-C', str(kernel), 'ARCH=arm', 'CROSS_COMPILE=' + str(compiler).removesuffix('gcc'),
                    'KERNELRELEASE=6.12.112', 'LOCALVERSION=', 'INSTALL_MOD_PATH=' + str(root),
                    'INSTALL_MOD_STRIP=1', 'DEPMOD=true', 'modules_install'], check=True,
                   stdout=log, stderr=subprocess.STDOUT)
modules = root / 'lib/modules/6.12.112'
for name in ('build', 'source'):
    (modules / name).unlink(missing_ok=True)
# OpenWrt's /sbin/modprobe is ubox kmodloader, whose module scan is not
# recursive. Keep this exact kernel's modules in OpenWrt's flat layout.
installed = sorted(modules.rglob('*.ko'))
for p in installed:
    destination = modules / p.name
    if p == destination:
        continue
    if destination.exists():
        assert destination.read_bytes() == p.read_bytes(), 'Conflicting kernel module basename: ' + p.name
        p.unlink()
    else:
        p.rename(destination)
for p in sorted(modules.rglob('*'), reverse=True):
    if p.is_dir() and not any(p.iterdir()):
        p.rmdir()
order = modules / 'modules.order'
order.write_text(''.join(Path(line).name + '\n' for line in order.read_text().splitlines()))
assert len(list(modules.glob('*.ko'))) == len({p.name for p in installed})
assert not any('/' in p.relative_to(modules).as_posix() for p in modules.rglob('*.ko'))
helper = work / 'busybox.armhf'
shutil.copyfile(combined / 'busybox.armhf', helper)
helper.chmod(0o755)
subprocess.run(['qemu-arm', str(helper), 'depmod', '-b', str(root), '6.12.112'], check=True)
old_modules = {Path(name).name for name in entries if name.endswith('.ko')}
new_modules = {p.name for p in modules.rglob('*.ko')}
builtin_modules = {Path(name).name for name in (modules / 'modules.builtin').read_text().splitlines()}
assert old_modules <= new_modules | builtin_modules, old_modules - new_modules - builtin_modules

defaults = root / 'etc/uci-defaults/98-ty1208z-docker-network'
defaults.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(project / 'openwrt/system/docker-network', defaults)
defaults.chmod(0o755)

# Preserve native accounts/configuration/language; mark this reduced bootstrap.
(root / 'etc/ty1208z-system-bootstrap').write_text('Native RAM bootstrap; load the verified userspace supplement before using Passwall or Docker.\n')
(root / 'etc/init.d/dockerd').unlink(missing_ok=True)
cpio = work / 'bootstrap.cpio'
subprocess.run([sys.executable, project / 'tools/make_initramfs.py', root, cpio], check=True)
compressor = source / 'staging_dir/host/bin/libdeflate-gzip'
with (output / 'rootfs.cpio.gz').open('wb') as handle:
    subprocess.run([compressor, '-12', '-c', cpio], stdout=handle, check=True)
compressed = (output / 'rootfs.cpio.gz').stat().st_size
assert compressed <= 512 * 65535 - 1 and cpio.stat().st_size <= 96 * 1024 * 1024
shutil.copyfile(kernel / 'arch/arm/boot/zImage', output / 'zImage')
shutil.copyfile(kernel / '.config', output / 'linux.config')
checks = output / 'checks'
checks.mkdir(exist_ok=True)
shutil.copyfile(build / 'kernel-layout.json', checks / 'kernel-layout.json')
shutil.copyfile(build / 'kernel-build.json', checks / 'kernel-build.json')
subprocess.run(['cpp', '-nostdinc', '-undef', '-x', 'assembler-with-cpp',
                '-I', str(project / 'overlay/arch/arm/boot/dts/hisilicon'), '-I', str(kernel / 'include'),
                '-DTY1208Z_INITRD_START=0x04000000', '-DTY1208Z_INITRD_END=' + hex(0x04000000 + compressed),
                str(project / 'openwrt/system/ram-rootfs.dts'), str(work / 'system.dts')], check=True)
subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', output / 'ty1208z-diagnostic.dtb', work / 'system.dts'], check=True)
(work / 'zImage-dtb').write_bytes((output / 'zImage').read_bytes() + (output / 'ty1208z-diagnostic.dtb').read_bytes())
subprocess.run(['mkimage', '-A', 'arm', '-O', 'linux', '-T', 'kernel', '-C', 'none',
                '-a', '0x02000000', '-e', '0x02000000', '-n', 'TY1208Z native system RAM',
                '-d', work / 'zImage-dtb', output / 'uImage-UNTESTED.bin'], check=True,
               env=dict(os.environ, SOURCE_DATE_EPOCH='1791676800'))

# Extend the already-prepared supplement with the omitted Xray and exact modules.
supplement_dir = work / 'native-userspace-supplement'
if not supplement_dir.exists():
    prepare(base_artifacts, combined, supplement_dir)
supplement = supplement_dir / 'userspace-supplement.RAM-ONLY.tar.gz'
supplement_manifest = json.loads((supplement_dir / 'manifest.json').read_bytes())
assert record(supplement.read_bytes()) == supplement_manifest['files'][supplement.name]
data = io.BytesIO()
delivered = {}
with tarfile.open(supplement, 'r:gz') as existing, tarfile.open(fileobj=data, mode='w', format=tarfile.PAX_FORMAT) as archive:
    for member in existing:
        payload = existing.extractfile(member) if member.isfile() else None
        archive.addfile(member, payload)
        delivered[member.name] = {'symlink': member.linkname} if member.issym() else {'bytes': member.size}
    additions = {'usr/bin/xray': entries['usr/bin/xray'][2]}
    for p in sorted(modules.rglob('*')):
        if p.is_file() and not p.is_symlink():
            additions[p.relative_to(root).as_posix()] = p.read_bytes()
    for name, payload in additions.items():
        assert name not in delivered, name
        member = tarfile.TarInfo(name)
        member.size, member.mode, member.mtime = len(payload), 0o755 if name == 'usr/bin/xray' else 0o644, 1791676800
        archive.addfile(member, io.BytesIO(payload))
        delivered[name] = record(payload)
network_payload = output / 'userspace-system.RAM-ONLY.tar.gz'
network_payload.write_bytes(gzip.compress(data.getvalue(), compresslevel=6, mtime=0))
files = {}
for p in sorted(output.rglob('*')):
    if p.is_file():
        with p.open('rb') as handle:
            files[p.relative_to(output).as_posix()] = {'bytes': p.stat().st_size, 'sha256': hashlib.file_digest(handle, 'sha256').hexdigest()}
receipt = {'schema': 1, 'status': 'integrated native RAM candidate; not booted or installable',
           'board': 'tianyi,ty1208z-ca-openwrt-system-ram', 'memory_end': 0x30000000,
           'kernel_patch_sha256': hashlib.sha256((project / 'patches/0001-hi3798mv100-diagnostic.patch').read_bytes()).hexdigest(),
           'bootstrap_omits': ['usr/bin/xray'], 'supplement': network_payload.name,
           'modules': len(new_modules), 'supplement_files': delivered,
           'module_layout': 'flat-openwrt-kmodloader',
           'storage': 'eMMC and SD request-level read-only; no automount',
           'package_database': 'bootstrap retained; supplement not registered; final native package integration pending',
           'prior_userspace_evidence': 'Unchanged cores/runtime and installed Passwall files; actual new-kernel runtime pending',
           'external_initrd': {'address': 0x4000000, 'bytes': compressed, 'uncompressed_bytes': cpio.stat().st_size},
           'persistent_writes': False, 'files': files}
(output / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'status': receipt['status'], 'bootstrap_bytes': compressed,
                  'supplement_bytes': network_payload.stat().st_size, 'modules': len(new_modules)}), flush=True)
