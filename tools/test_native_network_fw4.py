#!/usr/bin/env python3
"""Render real ARM fw4 rules with synthetic netifd state; never install rules."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from native_network import profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    name = profile(root)
    if name not in ('hybrid', 'nat'):
        raise ValueError('This test covers the two routed profiles')
    with tempfile.TemporaryDirectory(prefix='variant-fw4-') as directory:
        work = Path(directory)
        state = work / 'fw4.state'
        networks = {
            'probe': {'up': True, 'device': 'eth0', 'physdev': 'eth0',
                      'ipaddrs': [{'family': 4, 'addr': '192.0.2.2', 'mask': '255.255.255.0', 'bits': 24}]},
            'lan': {'up': True, 'device': 'br-wifi', 'physdev': 'br-wifi',
                    'ipaddrs': [{'family': 4, 'addr': '192.168.50.1', 'mask': '255.255.255.0', 'bits': 24}]},
        }
        state.write_text(json.dumps({'networks': networks, 'ubus_rules': []}))
        # Keep upstream fw4 logic intact. Redirect only its filesystem paths
        # and configuration cursor into the isolated offline root.
        source = (root / 'usr/share/ucode/fw4.uc').read_text()
        anchor = 'const STATEFILE = "/var/run/fw4.state";'
        assert source.count(anchor) == 1 and source.count('uci.cursor()') == 1
        source = source.replace(anchor, 'const STATEFILE = ' + json.dumps(str(state)) + ';')
        source = source.replace('uci.cursor()', 'uci.cursor(' + json.dumps(str(root / 'etc/config')) + ')')
        source = source.replace('/usr/share/firewall4/', str(root / 'usr/share/firewall4') + '/')
        (work / 'fw4.uc').write_text(source)
        script = work / 'render.uc'
        script.write_text('{% let fw4 = require("fw4"); fw4.load(true); include(' +
                          json.dumps(str(root / 'usr/share/firewall4/templates/ruleset.uc')) +
                          ', { fw4, type, exists, length, include }); %}\n')
        result = subprocess.run(['qemu-arm', '-L', str(root), str(root / 'usr/bin/ucode'),
                                 '-L', str(work / '*.uc'), '-L', str(root / 'usr/lib/ucode/*.so'),
                                 '-L', str(root / 'usr/share/ucode/*.uc'), '-T', str(script)],
                                capture_output=True, text=True, timeout=30,
                                env=dict(os.environ, QUIET='1'))
        assert result.returncode == 0, result.stderr
        rules = result.stdout

        def chain(label):
            match = re.search(r'\n\tchain ' + label + r' \{\n(.*?)\n\t\}', rules, re.S)
            assert match, label
            return match[1]

        assert 'iifname "eth0" jump forward_wan' in chain('forward')
        assert 'iifname "br-wifi" jump forward_lan' in chain('forward')
        assert 'jump accept_to_wan' in chain('forward_lan')
        assert 'oifname "eth0" jump srcnat_wan' in chain('srcnat')
        assert 'meta nfproto ipv4 masquerade' in chain('srcnat_wan')
        assert 'oifname "eth0" counter accept' in chain('accept_to_wan')
        if name == 'hybrid':
            assert 'jump accept_to_wan' in chain('forward_wan')
            assert 'jump accept_from_wan' in chain('input_wan')
        else:
            assert 'jump accept_to_wan' not in chain('forward_wan')
            assert 'jump drop_to_wan' in chain('forward_wan')
            assert 'jump reject_from_wan' in chain('input_wan')
    # fw4 may warn that host nft flowtable introspection is unavailable. No
    # nft rule is loaded, and this is neither a kernel nor traffic test.
    print('REAL_ARM_FW4_ROUTED_PROFILE_RENDER_AND_POLICY_PASS', name)


if __name__ == '__main__':
    main()
