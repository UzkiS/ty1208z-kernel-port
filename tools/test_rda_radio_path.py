#!/usr/bin/env python3
"""Exercise the radio migration with a real ARM UCI and a synthetic USB topology."""
import argparse
from pathlib import Path
import shlex
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
RDA = """config wifi-device 'radio0'
 option type 'rda'
 option path 'platform/soc/f9890000.usb/usb1/1-2'
 option disabled '1'
config wifi-iface 'default_radio0'
 option device 'radio0'
 option mode 'sta'
 option ssid 'Saved network'
 option encryption 'psk2'
 option key 'Saved password'
"""
DUPLICATE = """config wifi-device 'radio1'
 option type 'mac80211'
 option path 'platform/soc/f9890000.usb/usb2/2-2'
 option band '2g'
 option channel '1'
 option htmode 'NOHT'
 option country ''
 option num_global_macaddr ''
config wifi-iface 'default_radio1'
 option device 'radio1'
 option network 'lan'
 option mode 'ap'
 option ssid 'OpenWrt'
 option encryption 'none'
 option key ''
 option disabled '1'
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True,
                        help='Native runtime root containing the real ARM UCI')
    args = parser.parse_args()
    root = args.root.resolve()
    with tempfile.TemporaryDirectory(prefix='rda-radio-path-') as directory:
        work = Path(directory)
        sysfs = work / 'sys'
        device = sysfs / 'devices/platform/soc/f9890000.usb/usb2/2-2'
        device.mkdir(parents=True)
        (device / 'idVendor').write_text('1e04\n')
        (device / 'idProduct').write_text('8888\n')
        devices = sysfs / 'bus/usb/devices'
        devices.mkdir(parents=True)
        (devices / '2-2').symlink_to(device)
        config = work / 'config'
        config.mkdir()
        delta = work / 'delta'
        delta.mkdir()
        command = ['qemu-arm', '-L', str(root), str(root / 'sbin/uci'),
                   '-c', str(config), '-P', str(delta)]
        source = (PROJECT / 'openwrt/system/wireless/rda-path').read_text()
        source = source.replace('/sys/', str(sysfs) + '/').replace('/var/lock', str(work / 'lock'))
        script = work / 'run.sh'
        script.write_text('uci() { ' + shlex.join(command) + ' "$@"; }\n' + source)

        def get(*arguments):
            result = subprocess.run(command + ['-q', *arguments], capture_output=True, text=True)
            return result.stdout.strip()

        def run(text):
            (delta / 'wireless').unlink(missing_ok=True)
            (config / 'wireless').write_text(text)
            subprocess.run(['sh', script], check=True, timeout=30)
            first = (config / 'wireless').read_bytes()
            subprocess.run(['sh', script], check=True, timeout=30)
            assert (config / 'wireless').read_bytes() == first, 'Migration must be idempotent'
            assert get('get', 'wireless.radio0.path') == 'platform/soc/f9890000.usb/usb2/2-2'
            assert get('get', 'wireless.radio0.disabled') == '1'
            assert get('get', 'wireless.default_radio0.key') == 'Saved password'

        run(RDA + DUPLICATE)
        assert not get('get', 'wireless.radio1')
        assert not get('get', 'wireless.default_radio1')
        for index, customized in enumerate((
            DUPLICATE.replace("option ssid 'OpenWrt'", "option ssid 'User AP'"),
            DUPLICATE.replace("option disabled '1'", "option disabled '0'"),
            DUPLICATE + " option hidden '1'\n",
            DUPLICATE.replace('usb2/2-2', 'usb2/2-3'),
        )):
            run(RDA + customized)
            assert get('get', 'wireless.radio1') == 'wifi-device', (index, get('show', 'wireless'))
        (device / 'idProduct').write_text('9999\n')
        (delta / 'wireless').unlink(missing_ok=True)
        (config / 'wireless').write_text(RDA)
        subprocess.run(['sh', script], check=True, timeout=30)
        assert (config / 'wireless').read_text() == RDA, 'An unrelated USB device must not change config'
    print('RDA_RADIO_PATH_REAL_UCI_PASS: migration, idempotence, saved credentials, custom radios, USB identity')


if __name__ == '__main__':
    main()
