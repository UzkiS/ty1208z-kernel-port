#!/usr/bin/env python3
"""Check initial AP defaults and saved configuration preservation with ARM UCI."""
import argparse
from pathlib import Path
import shlex
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    with tempfile.TemporaryDirectory(prefix='wireless-defaults-') as directory:
        work = Path(directory)
        config, delta, override = (work / name for name in ('config', 'delta', 'override'))
        for path in (config, delta, override):
            path.mkdir()
        command = ['qemu-arm', '-L', str(root), str(root / 'sbin/uci'),
                   '-c', str(config), '-C', str(override), '-t', str(delta)]
        source = (PROJECT / 'openwrt/system/wireless/defaults').read_text()
        source = source.replace('/etc/config/wireless', str(config / 'wireless'))
        source = source.replace('exec /usr/libexec/ty1208z-rda-path', 'exit 0')
        script = work / 'run.sh'
        script.write_text('uci() { ' + shlex.join(command) + ' "$@"; }\n' + source)
        (config / 'network').write_text("config interface 'probe'\n option device 'eth0'\n option proto 'dhcp'\n"
                                       "config device 'saved_eth0'\n option name 'eth0'\n option macaddr '02:11:22:33:44:50'\n")
        (config / 'dhcp').touch()
        (config / 'firewall').write_text("config zone 'local'\n option name 'lan'\n list network 'lan'\n"
                                       "config zone 'uplink'\n option name 'wan'\n list network 'probe'\n")

        def run():
            subprocess.run(['sh', script], check=True, timeout=30)

        def get(key):
            return subprocess.check_output(command + ['get', key], text=True).strip()

        def firewall():
            script = work / 'firewall.sh'
            script.write_text('uci() { ' + shlex.join(command) + ' "$@"; }\n' +
                              (PROJECT / 'openwrt/system/docker-network').read_text())
            subprocess.run(['sh', script], check=True, timeout=30)

        run()
        for key, value in {
            'wireless.radio0.type': 'rda', 'wireless.radio0.disabled': '0',
            'wireless.default_radio0.mode': 'ap', 'wireless.default_radio0.ssid': 'TY1208Z',
            'wireless.default_radio0.encryption': 'none', 'wireless.default_radio0.network': 'probe',
            'network.probe.proto': 'dhcp', 'network.probe.device': 'br-uplink',
            'network.ty1208z_uplink.ports': 'eth0',
            'network.ty1208z_uplink.macaddr': '02:11:22:33:44:50',
        }.items():
            assert get(key) == value, key
        firewall()
        assert get('firewall.local.network') == 'lan probe'
        assert get('firewall.ty1208z_docker_wan.dest') == 'lan'
        result = subprocess.run(command + ['-q', 'get', 'firewall.uplink.network'], capture_output=True)
        assert b'probe' not in result.stdout
        before = {p.name: p.read_bytes() for p in config.iterdir()}
        run()
        assert before == {p.name: p.read_bytes() for p in config.iterdir()}
        # An upgrade keeps a custom/disabled STA, its secret, LAN, and DHCP.
        for key, value in {'wireless.radio0.disabled': '1', 'wireless.default_radio0.mode': 'sta',
                           'wireless.default_radio0.ssid': 'Saved network',
                           'wireless.default_radio0.key': 'Saved password'}.items():
            subprocess.run(command + ['set', key + '=' + value], check=True)
        subprocess.run(command + ['commit', 'wireless'], check=True)
        before = {p.name: p.read_bytes() for p in config.iterdir()}
        run()
        assert before == {p.name: p.read_bytes() for p in config.iterdir()}
        # Fresh wireless defaults must also keep an existing LAN and DHCP.
        (config / 'wireless').unlink()
        (config / 'network').write_text("config interface 'lan'\n option proto 'static'\n option ipaddr '192.0.2.1'\n")
        network = (config / 'network').read_bytes()
        dhcp = (config / 'dhcp').read_bytes()
        run()
        assert (config / 'network').read_bytes() == network
        assert (config / 'dhcp').read_bytes() == dhcp
        assert get('wireless.default_radio0.network') == 'lan'
        # Existing routed/STA profiles keep their Ethernet WAN behavior.
        subprocess.run(command + ['set', 'network.probe=interface'], check=True)
        subprocess.run(command + ['set', 'network.probe.device=eth0'], check=True)
        firewall()
        assert get('firewall.local.network') == 'lan'
        assert get('firewall.uplink.network') == 'probe'
        assert get('firewall.ty1208z_docker_wan.dest') == 'wan'
    print('WIRELESS_DEFAULTS_REAL_UCI_PASS: open AP, Ethernet bridge, saved MAC, idempotence, saved settings')


if __name__ == '__main__':
    main()
