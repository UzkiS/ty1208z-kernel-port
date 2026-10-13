#!/usr/bin/env python3
"""Record real ARM objects and the actual-function RO checks, not a boot image."""
import hashlib
import json
from pathlib import Path
import struct
import sys

root = Path(__file__).resolve().parents[1]
artifacts = Path(sys.argv[1]).resolve()
config = (artifacts / 'linux.config').read_text()
assert 'CONFIG_HI3798MV100_EMMC_READ_ONLY=y\n' in config
assert 'CONFIG_MMC_BLOCK_MINORS=16\n' in config
assert not list(artifacts.glob('*Image*')) and not list(artifacts.glob('*.dtb'))
for name in ('dw_mmc.o', 'dw_mmc-hi3798mv100-ident.o', 'block.o'):
    blob = (artifacts / name).read_bytes()
    assert blob[:6] == b'\x7fELF\x01\x01' and struct.unpack_from('<H', blob, 18)[0] == 40
    assert struct.unpack_from('<H', blob, 16)[0] == 1
log = (artifacts / 'checks/actual-policy.log').read_text()
for marker in ('EMMC_RO_POLICY_QUEUE_PASS:', 'EMMC_RO_SLOT_PASS:',
               'EMMC_RO_BLOCK_CORE_PASS: actual allocation/probe, RO=1;',
               'EMMC_RO_BLOCK_CORE_PASS: actual allocation/probe, RO=0;'):
    assert marker in log
paths = [p for p in artifacts.rglob('*') if p.is_file() and p.name != 'manifest.json']
files = {p.relative_to(artifacts).as_posix(): {'bytes': p.stat().st_size,
         'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths)}
sources = ('overlay/drivers/mmc/host/dw_mmc-hi3798mv100-ident.c',
           'overlay/drivers/mmc/host/hi3798mv100-emmc-ro-policy.h',
           'overlay/drivers/mmc/host/hi3798mv100-ident-policy.h',
           'tools/make_kernel_patch.py', 'tools/test_emmc_ro.py',
           'config/linux-emmc-ro.fragment', 'patches/0001-hi3798mv100-diagnostic.patch')
manifest = {'status': 'ARM objects and actual-function checks only; not hardware/boot acceptance',
            'boot_image': False, 'hardware_tested': False, 'files': files,
            'source_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources}}
(artifacts / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('EMMC_RO_COMPILE_ARTIFACTS_PASS: ARM objects, exact configuration, actual policy/block-core markers and source hashes')
