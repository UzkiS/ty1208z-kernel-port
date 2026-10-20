#!/usr/bin/env python3
"""Exercise all firmware network defaults using the actual ARM UCI binary."""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

import native_network


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Clean, unprofiled native disk root')
    original = parser.parse_args().root.resolve()
    with tempfile.TemporaryDirectory(prefix='network-profiles-') as directory:
        work = Path(directory)
        for name in native_network.PROFILES:
            root = work / name
            shutil.copytree(original / 'etc', root / 'etc', symlinks=True)
            for part in ('lib', 'sbin'):
                (root / part).symlink_to(original / part, target_is_directory=True)
            temporary = work / (name + '-uci')
            for part in ('override', 'delta'):
                (temporary / part).mkdir(parents=True)
            command = native_network.uci_command(root, temporary)

            def get(key):
                return subprocess.check_output(command + ['get', key], text=True).strip()

            before = {p.relative_to(root).as_posix(): p.read_bytes()
                      for p in (root / 'etc/config').iterdir() if p.is_file()}
            native_network.configure(root, name)
            assert native_network.profile(root) == name
            if name == 'bridge':
                assert all((root / key).read_bytes() == value for key, value in before.items())
            # Run the real first-boot network scripts in an isolated UCI root.
            # Supply a synthetic MAC so no host interface identity is consulted.
            for key, value in {'network.test_eth0': 'device', 'network.test_eth0.name': 'eth0',
                               'network.test_eth0.macaddr': '02:11:22:33:44:50'}.items():
                subprocess.run(command + ['set', key + '=' + value], check=True)
            subprocess.run(command + ['commit', 'network'], check=True)
            for filename in ('wireless/defaults', 'docker-network'):
                source = (native_network.PROJECT / 'openwrt/system' / filename).read_text()
                source = source.replace('exec /usr/libexec/ty1208z-rda-path', 'exit 0')
                source = source.replace('/etc/config/wireless', str(root / 'etc/config/wireless'))
                script = work / (name + '-' + filename.replace('/', '-') + '.sh')
                script.write_text('uci() { ' + shlex.join(command) + ' "$@"; }\n' + source)
                subprocess.run(['sh', script], check=True, timeout=30)
            assert get('wireless.default_radio0.mode') == 'ap'
            assert get('wireless.default_radio0.ssid') == 'TY1208Z'
            assert get('wireless.radio0.disabled') == '0'
            assert get('network.probe.proto') == 'dhcp'
            show = subprocess.check_output(command + ['show', 'firewall'], text=True)
            zones = [row.split('=')[0] for row in show.splitlines() if row.endswith('=zone')]
            zones = {get(zone + '.name'): zone for zone in zones}
            if name == 'bridge':
                assert get('network.probe.device') == 'br-uplink'
                assert get('network.ty1208z_uplink.ports') == 'eth0'
                assert get('wireless.default_radio0.network') == 'probe'
                assert get('firewall.ty1208z_docker_wan.dest') == 'lan'
            else:
                assert get('network.probe.device') == 'eth0'
                assert get('network.lan.device') == 'br-wifi'
                assert get('network.lan.ipaddr') == native_network.WIFI_ADDRESS
                assert get('wireless.default_radio0.network') == 'lan'
                assert get('dhcp.lan.ignore') == '0' and get('dhcp.probe.ignore') == '1'
                assert get('dhcp.lan.ra') == 'disabled'
                assert get(zones['wan'] + '.masq') == '1'
                assert get(zones['wan'] + '.network').split().count('probe') == 1
                assert 'probe' not in get(zones['lan'] + '.network').split()
                assert get(zones['wan'] + '.input') == ('ACCEPT' if name == 'hybrid' else 'REJECT')
                assert get(zones['wan'] + '.forward') == ('ACCEPT' if name == 'hybrid' else 'DROP')
                assert get('firewall.ty1208z_docker_wan.dest') == 'wan'
                if name == 'hybrid':
                    terminal = subprocess.run(command + ['-q', 'get', 'ttyd.@ttyd[0].interface'], capture_output=True)
                    assert terminal.returncode == 1 and not terminal.stdout
                else:
                    assert get('ttyd.@ttyd[0].interface') == '@lan'
                sysctl = (root / 'etc/sysctl.conf').read_text()
                assert 'net.ipv4.conf.eth0.send_redirects=0\n' in sysctl
                # No upstream ethernet membership in the downstream bridge.
                ports = subprocess.run(command + ['-q', 'get', 'network.ty1208z_wifi.ports'], capture_output=True)
                assert ports.returncode != 0 and b'eth0' not in ports.stdout
            try:
                native_network.configure(root, name)
            except ValueError:
                pass
            else:
                raise AssertionError('Repeated application could overwrite saved configuration')
            assert json.loads((root / native_network.MARKER).read_bytes())['profile'] == name
    print('THREE_NETWORK_PROFILES_REAL_ARM_UCI_FIRSTBOOT_DHCP_FIREWALL_DOCKER_PASS')


if __name__ == '__main__':
    main()
