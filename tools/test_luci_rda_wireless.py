#!/usr/bin/env python3
"""Run the real pinned LuCI modal builder with the RDA radio and form API stubs."""
import argparse
from pathlib import Path
import subprocess

JAVASCRIPT = r'''
const fs = require('fs'), assert = require('assert');
const text = fs.readFileSync(process.argv[1], 'utf8');
const start = text.indexOf('s.addModalOptions = function(s) {');
const end = text.indexOf('\n\t\ts.handleRemove = function', start);
assert(start >= 0 && end > start);
const sections = [];
class Section {
    constructor() { this.children = []; sections.push(this); }
    tab() {}
    taboption(tab, type, name) { return this.option(type, name); }
    option(type, name) {
        const o = { option: name, keylist: [], vallist: [], deps: [], section: this,
            value(k, v) { this.keylist.push(k); this.vallist.push(v); },
            depends(a, b) { this.deps.push(typeof a == 'object' ? a : {[a]: b}); },
            formvalue() { return this.option == 'encryption' ? 'psk2' : 'ccmp'; },
            isActive() { return true; }
        };
        if (type == 'section') o.subsection = new Section();
        this.children.push(o); return o;
    }
}
const values = {};
const uci = { get(c, s, k) { return k == 'type' ? 'rda' : k == 'band' ? '2g' : undefined; },
    set(c, s, k, v) { values[k] = v; }, unset() {} };
const radio = { getWifiDeviceName() { return 'radio0'; }, getName() { return 'wlan0'; }, get() {} };
const network = { getWifiNetwork() { return Promise.resolve(radio); } };
const form = new Proxy({SectionValue: 'section'}, {get(o, k) { return o[k] || k; }});
const L = { hasSystemFeature() { return false; }, bind(fn) { return fn; }, url() { return ''; } };
const ui = {createHandlerFn() { return () => {}; }};
const widgets = {};
const _ = x => x;
function add_dependency_permutations() {}
function network_updown() {}
function CBIWifiFrequencyValue() {}
function CBIWifiTxPowerValue() {}
function CBIWifiCountryValue() {}
String.prototype.format = function() { return String(this); };
const s = new Section(); s.section = 'default_radio0';
eval(text.slice(start, end));
s.addModalOptions(s).then(() => {
    const device = sections[1], iface = sections[2];
    const option = (section, name) => section.children.find(o => o.option == name);
    assert.deepStrictEqual(option(device, 'band').keylist, ['2g']);
    assert.deepStrictEqual(option(device, 'htmode').keylist, ['HT20', 'NONE']);
    assert.deepStrictEqual(option(device, 'channel').keylist, Array.from({length:13}, (_, i) => String(i+1)));
    assert(!option(device, '_freq'));
    assert.deepStrictEqual(option(iface, 'mode').keylist, ['ap', 'sta']);
    assert.deepStrictEqual(option(iface, 'encryption').keylist, ['psk2', 'none']);
    assert.deepStrictEqual(option(iface, 'cipher').keylist, ['auto', 'ccmp']);
    assert(!option(iface, 'ppsk') && !option(iface, 'ieee80211r'));
    const key = option(iface, '_wpa_key');
    assert.deepStrictEqual(key.deps, [{mode:'ap', encryption:'psk2'}, {mode:'sta', encryption:'psk2'}]);
    option(iface, 'encryption').write('default_radio0', 'psk2');
    assert.strictEqual(values.encryption, 'psk2+ccmp');
    console.log('LUCI_RDA_ACTUAL_FORM_PASS');
}).catch(e => { console.error(e); process.exitCode = 1; });
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--node", default="node")
    args = parser.parse_args()
    subprocess.run([args.node, "-e", JAVASCRIPT, str(args.source)], check=True, timeout=15)


if __name__ == "__main__":
    main()
