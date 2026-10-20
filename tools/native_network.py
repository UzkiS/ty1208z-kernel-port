"""Prepare network defaults in an offline root, before its reset snapshot."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
PROFILES = ('bridge', 'hybrid', 'nat')
MARKER = 'usr/share/ty1208z-network/profile.json'
WIFI_ADDRESS = '192.168.50.1'


def source_identity():
    path = Path(__file__)
    return {path.relative_to(PROJECT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()}


def profile(root):
    path = root / MARKER
    return json.loads(path.read_bytes())['profile'] if path.exists() else None


def uci_command(root, temporary):
    # All paths are explicit: never read/write the host's UCI configuration.
    return ['qemu-arm', '-L', str(root), str(root / 'sbin/uci'),
            '-c', str(root / 'etc/config'), '-C', str(temporary / 'override'),
            '-t', str(temporary / 'delta')]


def configure(root, name):
    if name not in PROFILES:
        raise ValueError('Unknown network profile: ' + name)
    if (root / MARKER).exists():
        raise ValueError('Network defaults require a fresh, unprofiled staging root')
    # bridge deliberately retains the existing first-boot scripts and defaults.
    if name != 'bridge':
        (root / 'etc/config/wireless').touch(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='ty1208z-network-') as directory:
            temporary = Path(directory)
            for part in ('override', 'delta'):
                (temporary / part).mkdir()
            command = uci_command(root, temporary)

            def get(key):
                return subprocess.check_output(command + ['get', key], text=True).strip()

            if get('network.probe.proto') != 'dhcp' or get('network.probe.device') != 'eth0':
                raise ValueError('Expected the clean single-port DHCP uplink baseline')
            # This is a build-time operation on clean firmware defaults, never
            # an upgrade-time script which could replace saved user settings.
            lines = [
                "set network.probe.peerdns='1'",
                "set network.lan=interface", "set network.lan.device='br-wifi'",
                "set network.lan.proto='static'", "set network.lan.ipaddr='" + WIFI_ADDRESS + "'",
                "set network.lan.netmask='255.255.255.0'",
                "set network.ty1208z_wifi=device", "set network.ty1208z_wifi.name='br-wifi'",
                "set network.ty1208z_wifi.type='bridge'", "set network.ty1208z_wifi.bridge_empty='1'",
                "set wireless.radio0=wifi-device", "set wireless.radio0.type='rda'",
                "set wireless.radio0.band='2g'", "set wireless.radio0.channel='6'",
                "set wireless.radio0.htmode='HT20'", "set wireless.radio0.disabled='0'",
                "set wireless.default_radio0=wifi-iface", "set wireless.default_radio0.device='radio0'",
                "set wireless.default_radio0.mode='ap'", "set wireless.default_radio0.network='lan'",
                "set wireless.default_radio0.ssid='TY1208Z'", "set wireless.default_radio0.encryption='none'",
                "set dhcp.lan=dhcp", "set dhcp.lan.interface='lan'", "set dhcp.lan.ignore='0'",
                "set dhcp.lan.start='100'", "set dhcp.lan.limit='150'", "set dhcp.lan.leasetime='12h'",
                "set dhcp.probe=dhcp", "set dhcp.probe.interface='probe'", "set dhcp.probe.ignore='1'",
                # No upstream RA is bridged onto Wi-Fi. IPv6 prefix delegation
                # is a separate user configuration, not accidental IPv4 bypass.
                "set dhcp.lan.ra='disabled'", "set dhcp.lan.dhcpv6='disabled'",
                "set dhcp.lan.ndp='disabled'",
                # Hybrid management is available on Ethernet and Wi-Fi;
                # the firewall defines the permitted ingress. Pure NAT keeps
                # the terminal bound to its downstream LAN device.
                "set ttyd.@ttyd[0].interface='" + ('' if name == 'hybrid' else '@lan') + "'",
            ]
            # Retain stock firewall rules and package-owned configuration, but
            # assign each L3 interface to exactly one zone.
            show = subprocess.check_output(command + ['show', 'firewall'], text=True)
            zones = [line.split('=', 1)[0] for line in show.splitlines() if line.endswith('=zone')]
            named = {get(zone + '.name'): zone for zone in zones}
            if not {'lan', 'wan'} <= named.keys():
                raise ValueError('Native LAN/WAN firewall zones missing')
            lan, wan = named['lan'], named['wan']
            # UCI delete with -q is allowed to fail for absent optional lists.
            for zone in zones:
                networks = subprocess.run(command + ['-q', 'get', zone + '.network'], capture_output=True, text=True)
                if 'probe' in networks.stdout.split():
                    subprocess.run(command + ['del_list', zone + '.network=probe'], check=True)
            lines += [
                "add_list " + wan + ".network='probe'",
                "set " + wan + ".masq='1'", "set " + wan + ".mtu_fix='1'",
                "set " + wan + ".input='" + ('ACCEPT' if name == 'hybrid' else 'REJECT') + "'",
                "set " + wan + ".forward='" + ('ACCEPT' if name == 'hybrid' else 'DROP') + "'",
                "set " + lan + ".input='ACCEPT'", "set " + lan + ".forward='ACCEPT'",
                "commit network", "commit wireless", "commit dhcp", "commit firewall", "commit ttyd",
            ]
            result = subprocess.run(command + ['batch'], input='\n'.join(lines) + '\n',
                                    text=True, capture_output=True, check=True)
            if result.stderr.strip():
                raise ValueError('UCI rejected network defaults: ' + result.stderr)
        # Keep these in the backed-up user sysctl file. A cross-profile upgrade
        # retaining /etc must retain the old network behavior as well.
        sysctl = root / 'etc/sysctl.conf'
        sysctl.write_text(sysctl.read_text() + '\n# TY1208Z routed network defaults\n'
                          'net.ipv4.ip_forward=1\n'
                          'net.ipv4.conf.all.send_redirects=0\n'
                          'net.ipv4.conf.default.send_redirects=0\n'
                          'net.ipv4.conf.eth0.send_redirects=0\n')
    marker = root / MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({'schema': 1, 'profile': name,
                                 'wifi_ipv4': None if name == 'bridge' else WIFI_ADDRESS + '/24',
                                 'meaning': 'Firmware defaults; retained user configuration may differ'},
                                indent=2) + '\n')


def make_package(apk, root, output):
    """Own the immutable default-profile marker without owning user settings."""
    payload = (root / MARKER).read_bytes()
    files = output / 'files'
    marker = files / MARKER
    marker.parent.mkdir(parents=True)
    marker.write_bytes(payload)
    identity = hashlib.sha256(payload).hexdigest()[:12]
    package = output / ('ty1208z-network-1.0~' + identity + '-r1.apk')
    subprocess.run([str(apk), 'mkpkg', '--files', str(files), '--output', str(package),
                    '--info', 'name:ty1208z-network', '--info', 'version:1.0~' + identity + '-r1',
                    '--info', 'arch:arm_cortex-a7_neon-vfpv4', '--info', 'license:GPL-2.0-only',
                    '--info', 'description:TY1208Z firmware network profile identity'], check=True)
    return package
