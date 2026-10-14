#!/usr/bin/env python3
"""Run the actual guest script in its selected ARM shell with synthetic sysfs."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from board_diag_cli import EMMC_RO_DIAGNOSTIC

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ((0, 2048), (2048, 2048), (4096, 8192), (12288, 8192), (20480, 8192),
          (28672, 40960), (69632, 131072), (200704, 1048576), (1249280, 14020608))


def test(busybox):
    applets = subprocess.check_output(['qemu-arm', str(busybox), '--list'], text=True).splitlines()
    assert {'sh', 'sha256sum', 'cat', 'grep', 'awk', 'ls', 'mkdir', 'rm', 'mount', 'umount'} <= set(applets)
    source = (ROOT / 'initramfs/emmc-ro-diag').read_text()
    for mode in ('success', 'foreign-board', 'writable', 'wrong-size', 'wrong-partition',
                 'boot-area', 'preexisting-mount', 'mount-failed', 'file-read-failed'):
        with tempfile.TemporaryDirectory(prefix='emmc-ro-guest-') as directory:
            path = Path(directory)
            sysfs = path / 'sys'
            compatible = sysfs / 'firmware/devicetree/base/compatible'
            compatible.parent.mkdir(parents=True)
            compatible.write_bytes(b'foreign\0' if mode == 'foreign-board' else
                                   b'tianyi,ty1208z-ca-emmc-ro-ram\0hi3798mv100-series\0')
            blocks = sysfs / 'class/block'
            for index, (start, size) in enumerate(((0, 15269888), *LAYOUT)):
                block = blocks / ('mmcblk0' if index == 0 else f'mmcblk0p{index}')
                block.mkdir(parents=True)
                (block / 'ro').write_text('0\n' if mode == 'writable' and index == 0 else '1\n')
                (block / 'start').write_text(str(start + (mode == 'wrong-partition' and index == 9)) + '\n')
                (block / 'size').write_text(str(size - (mode == 'wrong-size' and index == 0)) + '\n')
            if mode == 'boot-area':
                extra = blocks / 'mmcblk0boot0'
                extra.mkdir()
                (extra / 'ro').write_text('1\n')
            mounts = path / 'mounts'
            mounts.write_text('/dev/mmcblk0p9 /existing ext4 ro 0 0\n' if mode == 'preexisting-mount' else '')
            target, state = path / 'mount', path / 'state'
            script = source.replace('/sys/', str(sysfs) + '/').replace('/proc/mounts', str(mounts))
            script = script.replace('/tmp/emmc-ro-mount', str(target))
            wrappers = f'''
mount() {{
    test "$*" = "-t ext4 -o ro,noload /dev/mmcblk0p9 {target}" || exit 90
    test "{mode}" != mount-failed || return 1
    echo mounted > "{state}"
}}
umount() {{
    test "$*" = "{target}" && test -f "{state}" || exit 91
    rm "{state}"
}}
emmc-ro-probe() {{
    case "$*" in
        --blocks) echo SYNTHETIC_BLOCK_PROBE ;;
        "--mounted {target}")
            test -f "{state}" || exit 92
            test "{mode}" != file-read-failed || return 1
            echo SYNTHETIC_FILE_PROBE ;;
        *) exit 93 ;;
    esac
}}
'''
            result = subprocess.run(['qemu-arm', str(busybox), 'sh', '-s'], input=wrappers + script,
                                    text=True, capture_output=True, timeout=10)
            assert result.returncode == (0 if mode == 'success' else 1), (mode, result.stdout, result.stderr)
            assert not target.exists() and not state.exists(), (mode, 'mount/directory cleanup failed')
            if mode == 'success':
                assert 'EMMC_RO_DIAG_COMPLETE partitions=9 filesystems=1 no-card-writes' in result.stdout
            else:
                assert 'EMMC_RO_DIAG_COMPLETE' not in result.stdout
    marker = 'EMMC_RO_FS_FILE_READ_PASS bytes=444 content-and-name-excluded'
    with tempfile.TemporaryDirectory(prefix='emmc-ro-uart-') as directory:
        path = Path(directory) / 'report'
        command = EMMC_RO_DIAGNOSTIC.decode().replace('/tmp/emmc-ro-report', str(path))
        wrappers = '''
emmc-ro-diag() {
    printf 'EMMC_RO_FS_FILE_READ_PASS bytes=4'
    printf '[kernel] ext4 unmount printk\n' >&2
    printf '44 content-and-name-excluded\n'
}
diag() { echo RAM_DIAG; }
'''
        # Reproduce the observed console interleaving with the actual ARM shell.
        old = subprocess.run(['qemu-arm', str(busybox), 'sh', '-s'],
                             input=wrappers + 'emmc-ro-diag; diag\n', text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        assert old.returncode == 0 and marker not in old.stdout.splitlines()
        result = subprocess.run(['qemu-arm', str(busybox), 'sh', '-s'], input=wrappers + command,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        assert result.returncode == 0 and result.stdout.splitlines().count(marker) == 1
        assert not path.exists()
        # A preexisting report must not be accepted, emitted or removed.
        path.write_text(marker + '\n')
        refused = subprocess.run(['qemu-arm', str(busybox), 'sh', '-s'], input=wrappers + command,
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        assert refused.returncode == 0 and refused.stdout == 'RAM_DIAG\n'
        assert path.read_text() == marker + '\n'
        path.unlink()
        failed = subprocess.run(['qemu-arm', str(busybox), 'sh', '-s'],
                                input='emmc-ro-diag() { echo INCOMPLETE; return 1; }; diag() { :; };\n' + command,
                                text=True, capture_output=True, timeout=10)
        assert failed.stdout == 'INCOMPLETE\n' and not path.exists()
    print('EMMC_RO_UART_BUFFER_PASS actual ARM shell: interleaved printk reproduction, intact buffered marker, stale-report refusal and failure cleanup')
    print('EMMC_RO_ARM_GUEST_PASS actual shell/applets, exact board/RO/layout guards, ro,noload arguments and failure cleanup; synthetic files only')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--busybox', type=Path, required=True)
    test(parser.parse_args().busybox)
