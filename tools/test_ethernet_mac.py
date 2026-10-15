#!/usr/bin/env python3
"""Check per-device DHCP MAC persistence with real ARM UCI and synthetic sysfs."""
import argparse
from pathlib import Path
import shlex
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
NETWORK = """config interface 'probe'
 option device 'eth0'
 option proto 'dhcp'
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    with tempfile.TemporaryDirectory(prefix='ethernet-mac-') as directory:
        work = Path(directory)
        sysfs = work / 'sys/class/net/eth0'
        sysfs.mkdir(parents=True)
        config, delta = work / 'config', work / 'delta'
        config.mkdir()
        delta.mkdir()
        override = work / 'override'
        override.mkdir()
        command = ['qemu-arm', '-L', str(root), str(root / 'sbin/uci'),
                   '-c', str(config), '-C', str(override), '-t', str(delta)]
        source = (PROJECT / 'openwrt/system/ethernet-mac').read_text()
        source = source.replace('/sys/', str(work / 'sys') + '/')
        script = work / 'run.sh'
        script.write_text('uci() { ' + shlex.join(command) + ' "$@"; }\n' + source)

        def run(network, address='02:11:22:33:44:50', kind='1', expected=0):
            (delta / 'network').unlink(missing_ok=True)
            (config / 'network').write_text(network)
            (sysfs / 'address').write_text(address + '\n')
            (sysfs / 'addr_assign_type').write_text(kind + '\n')
            result = subprocess.run(['sh', script], timeout=30)
            assert result.returncode == expected, (address, kind, result.returncode)
            return (config / 'network').read_text()

        first = run(NETWORK)
        assert "option macaddr '02:11:22:33:44:50'" in first
        # Next boot has a new fallback address, but the saved identity wins.
        assert run(first, address='02:11:22:33:44:52') == first
        assert run(NETWORK, address='02:11:22:33:44:54') != first
        for extra in (
            " option macaddr '02:aa:bb:cc:dd:ee'\n",
            "config device 'custom'\n option name 'eth0'\n option macaddr '02:aa:bb:cc:dd:ee'\n",
        ):
            assert run(NETWORK + extra) == NETWORK + extra
        existing = NETWORK + "config device 'custom'\n option name 'eth0'\n option mtu '1400'\n"
        changed = run(existing)
        assert "config device 'custom'" in changed and 'ty1208z_eth0' not in changed
        assert "option mtu '1400'" in changed
        legacy = NETWORK.replace("option device 'eth0'", "option ifname 'eth0'")
        legacy += " option macaddr '02:aa:bb:cc:dd:ee'\n"
        assert run(legacy) == legacy
        unrelated = NETWORK + "config device 'other'\n option name 'eth1'\n option macaddr '02:aa:bb:cc:dd:ee'\n"
        assert "option macaddr '02:11:22:33:44:50'" in run(unrelated)
        for address in ('00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff', '01:11:22:33:44:50', 'invalid'):
            assert run(NETWORK, address=address, expected=1) == NETWORK
        assert run(NETWORK, kind='0') == NETWORK
        assert run(NETWORK, kind='3') == NETWORK
        collision = NETWORK + "config interface 'ty1208z_eth0'\n option device 'eth1'\n"
        assert run(collision, expected=1) == collision
    print('ETHERNET_MAC_REAL_UCI_PASS: per-device persistence, reboot identity, user overrides, validation')


if __name__ == '__main__':
    main()
