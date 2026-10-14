"""Keep native Docker payloads, with bounded recovery from slow cold storage."""
import json
from pathlib import Path
import subprocess


def patched_init(text):
    before = '\tprocess_config\n\n\tprocd_open_instance\n'
    after = ('\tprocess_config\n\n'
             '\t# Managed containerd has a 15-second startup deadline. Read its\n'
             '\t# executable before that deadline starts on the bounded PIO host.\n'
             '\tcat /usr/bin/containerd >/dev/null || return 1\n\n'
             '\tprocd_open_instance\n')
    if after not in text:
        if text.count(before) != 1:
            raise ValueError('Native dockerd prestart anchor changed')
        text = text.replace(before, after)
    before = '\tprocd_set_param limits nofile="${nofile} ${nofile}"\n'
    after = before + '\tprocd_set_param respawn 3600 10 3\n'
    if after not in text:
        if text.count(before) != 1:
            raise ValueError('Native dockerd respawn anchor changed')
        text = text.replace(before, after)
    return text


def make_package(apk, original, output):
    """Repackage the pinned native APK without rebuilding/changing the engine."""
    output = Path(output)
    output.mkdir(parents=True)
    info = json.loads(subprocess.check_output([apk, 'adbdump', '--format', 'json', original]))
    assert info['info']['name'] == 'dockerd' and info['info']['version'] == '29.6.1-r1'
    assert not info.get('triggers'), 'Review new upstream triggers before repacking'
    files = output / 'files'
    files.mkdir()
    subprocess.run([apk, 'extract', '--allow-untrusted', '--no-chown', '--destination', files, original], check=True)
    init = files / 'etc/init.d/dockerd'
    init.write_text(patched_init(init.read_text()))
    package = output / 'dockerd-29.6.1-r2.apk'
    command = [apk, 'mkpkg', '--files', files, '--output', package]
    for key, value in info['info'].items():
        if key in ('hashes', 'installed-size'):
            continue
        if key == 'version':
            value = '29.6.1-r2'
        if isinstance(value, list):
            value = ' '.join(value)
        command += ['--info', key + ':' + str(value)]
    for kind, script in info.get('scripts', {}).items():
        path = output / kind
        path.write_text(script)
        command += ['--script', kind + ':' + str(path)]
    subprocess.run(command, check=True)
    return package
