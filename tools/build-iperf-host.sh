#!/bin/bash
# Pinned host test peer; build in the taskbase, never install system files.
set -euo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd)
taskbase=${1:-"$project/.work"}
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export SOURCE_DATE_EPOCH=1791676800
source_tree=$(python3 - "$project" "$taskbase" <<'PY'
import json, sys, urllib.error, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'tools'))
from prepare_openwrt import extract, sha256
project, base = map(Path, sys.argv[1:])
item = json.loads((project / 'openwrt/ethernet/sources.lock.json').read_text())['iperf3']
archive = base / 'downloads' / item['archive']
archive.parent.mkdir(parents=True, exist_ok=True)
if not archive.exists():
    partial = archive.with_suffix(archive.suffix + '.partial')
    for url in [*item.get('mirrors', []), item['url']]:
        try:
            urllib.request.urlretrieve(url, partial)
            break
        except urllib.error.URLError:
            continue
    else:
        raise ValueError('No pinned iperf source mirror was available')
    if sha256(partial) != item['sha256']:
        raise ValueError('Downloaded iperf host source hash differs')
    partial.replace(archive)
if sha256(archive) != item['sha256']:
    raise ValueError('Cached iperf host source hash differs')
destination = base / 'build/iperf3-host-3.20'
marker = destination / '.ty1208z-source.json'
if destination.exists():
    if not marker.exists() or json.loads(marker.read_text()) != item:
        raise ValueError('Unrecognized iperf host directory')
else:
    destination.mkdir(parents=True)
    extract(archive, destination, 'iperf-3.20')
    marker.write_text(json.dumps(item, indent=2) + '\n')
print(destination)
PY
)
cd "$source_tree"
./configure --disable-shared --without-openssl --without-sctp
make -j"${JOBS:-4}"
./src/iperf3 --version
python3 - "$source_tree/src/iperf3" "$project/artifacts/iperf-host/manifest.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
binary, output = map(Path, sys.argv[1:])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({'version': '3.20', 'binary': str(binary),
                             'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2) + '\n')
PY
