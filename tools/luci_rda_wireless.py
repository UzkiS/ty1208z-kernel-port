#!/usr/bin/env python3
"""Adapt the pinned official LuCI wireless form to the RDA backend's limits."""
import hashlib
from pathlib import Path

RELATIVE = Path("modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js")
ORIGINAL_SHA256 = "6385cebb2b415257d05def51e890620d7e6b9f8b14071a374ed9dc2ed392c45f"
PATCHED_SHA256 = "349dfd408d956a4fdc35ffd059ba03758ce96da2cee7413bfaf74dd803f52d42"
MARKER = "// TY1208Z RDA: expose only backend-supported settings."


def transform(original):
    def replace(before, after):
        nonlocal original
        if original.count(before) != 1:
            raise ValueError("Pinned LuCI RDA anchor changed: " + before[:100])
        original = original.replace(before, after)

    replace("\t\t\t\to.ucisection = s.section;\n",
            "\t\t\t\to.ucisection = s.section;\n" + '''
\t\t\t\tif (hwtype == 'rda') {
\t\t\t\t\tss.children = ss.children.filter(opt => opt.option != '_freq');
\t\t\t\t\to = ss.taboption('general', form.ListValue, 'band', _('Band'));
\t\t\t\t\to.value('2g', '2.4 GHz');
\t\t\t\t\to.default = '2g';
\t\t\t\t\to.rmempty = false;
\t\t\t\t\to = ss.taboption('general', form.ListValue, 'htmode', _('Width'));
\t\t\t\t\to.value('HT20', '20 MHz');
\t\t\t\t\to.value('NONE', _('Legacy'));
\t\t\t\t\to.default = 'HT20';
\t\t\t\t\to.rmempty = false;
\t\t\t\t\to = ss.taboption('general', form.ListValue, 'channel', _('Channel'));
\t\t\t\t\tfor (let ch = 1; ch <= 13; ch++)
\t\t\t\t\t\to.value(String(ch), String(ch));
\t\t\t\t\to.default = '6';
\t\t\t\t\to.rmempty = false;
\t\t\t\t}
''')
    replace("!have_mesh ? '<a id=\"installmesh\"", "hwtype != 'rda' && !have_mesh ? '<a id=\"installmesh\"")
    replace("\t\t\t\to.value('adhoc', _('Ad-Hoc'));",
            "\t\t\t\tif (hwtype != 'rda')\n\t\t\t\t\to.value('adhoc', _('Ad-Hoc'));")
    replace("\t\t\t\telse if (hwtype == 'broadcom') {",
            "\t\t\t\telse if (hwtype == 'rda') {\n"
            "\t\t\t\t\tcrypto_modes.push(['psk2', 'WPA2-PSK', 33]);\n\t\t\t\t}\n"
            "\t\t\t\telse if (hwtype == 'broadcom') {")
    replace("\t\t\t});\n\t\t};\n\n\t\ts.handleRemove = function", '''
\t\t\t\tif (hwtype == 'rda') {
\t\t\t\t\t// TY1208Z RDA: expose only backend-supported settings.
\t\t\t\t\tconst supported = ['mode', 'ssid', 'network', 'hidden', 'encryption', 'cipher', '_qrops', '_wpa_key'];
\t\t\t\t\tss.children = ss.children.filter(opt => supported.includes(opt.option));
\t\t\t\t\tconst cipher = ss.children.find(opt => opt.option == 'cipher');
\t\t\t\t\tcipher.keylist = ['auto', 'ccmp'];
\t\t\t\t\tcipher.vallist = [_('auto'), _('Force CCMP (AES)')];
\t\t\t\t\tconst key = ss.children.find(opt => opt.option == '_wpa_key');
\t\t\t\t\tkey.deps = [{ mode: 'ap', encryption: 'psk2' }, { mode: 'sta', encryption: 'psk2' }];
\t\t\t\t}
\t\t\t});
\t\t};

\t\ts.handleRemove = function''')
    return original


def apply(feed):
    path = feed / RELATIVE
    original = path.read_text()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest == PATCHED_SHA256:
        return path
    if digest != ORIGINAL_SHA256:
        raise ValueError("Pinned official LuCI wireless source identity changed")
    path.write_text(transform(original))
    return path
