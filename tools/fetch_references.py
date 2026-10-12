#!/usr/bin/env python3
"""Fetch selected, pinned vendor references without executing vendor scripts."""
import concurrent.futures
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'a9f05973129d738e175416dd4a91b2c264ffcdd4'
BASE = f'https://raw.githubusercontent.com/07bug/HiSTBLinuxV100R005C00SPC060/{COMMIT}/source/kernel/linux-4.4.y.patch/'


def fetch(item):
    name = item['path']
    for attempt in range(3):
        try:
            with urllib.request.urlopen(BASE + name, timeout=30) as response:
                data = response.read()
            git_sha = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
            if git_sha != item['sha']:
                raise ValueError(f'Git blob checksum mismatch: {name}')
            target = ROOT / 'reference/sdk' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return {'path': name, 'bytes': len(data), 'git_blob_sha1': git_sha, 'sha256': hashlib.sha256(data).hexdigest(), 'url': BASE + name}
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def main():
    manifest = json.loads((ROOT / 'reference/reference-manifest.json').read_text(encoding='utf-8'))
    assert manifest['commit'] == COMMIT, 'Unexpected vendor reference commit'
    selected = [{'path': item['path'], 'sha': item['git_blob_sha1']} for item in manifest['files']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        entries = list(pool.map(fetch, selected))
    report = {'repository': '07bug/HiSTBLinuxV100R005C00SPC060', 'commit': COMMIT, 'patch_tree': manifest['patch_tree'], 'files': entries}
    (ROOT / 'reference/reference-manifest.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'Verified and stored {len(entries)} pinned SDK reference files ({sum(x["bytes"] for x in entries)} bytes).')


if __name__ == '__main__':
    main()
