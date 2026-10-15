#!/usr/bin/env python3
"""Stage the complete vendored RDA tree; optionally verify upstream downloads."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "reference/wifi-rda-usb.lock.json"
VENDOR = ROOT / "wifi/vendor/rdaw80211"


def load_lock(path=LOCK):
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema") != 1 or not re.fullmatch(r"[0-9a-f]{40}", lock["commit"]):
        raise ValueError("Invalid source lock schema or commit")
    repository = lock["repository"]
    if not re.fullmatch(r"https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Expected a pinned GitHub repository")
    prefix = lock["prefix"]
    if not re.fullmatch(r"[A-Za-z0-9_/-]+", prefix) or ".." in prefix.split("/"):
        raise ValueError("Invalid upstream directory")
    base = repository.replace("https://github.com/", "https://raw.githubusercontent.com/")
    base += f"/{lock['commit']}/{prefix}/"
    seen = set()
    for item in lock["files"]:
        name = item["path"]
        rel = PurePosixPath(name)
        if (not re.fullmatch(r"[A-Za-z0-9_./-]+", name) or rel.is_absolute()
                or ".." in rel.parts or str(rel) != name or name in seen):
            raise ValueError(f"Invalid or repeated source path: {name}")
        seen.add(name)
        if item["url"] != base + name:
            raise ValueError(f"URL differs from pinned repository: {name}")
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError(f"Invalid SHA-256: {name}")
        if type(item["bytes"]) is not int or not 0 < item["bytes"] <= 8 * 1024 * 1024:
            raise ValueError(f"Invalid source size: {name}")
        if "git_blob_sha" in item and not re.fullmatch(r"[0-9a-f]{40}", item["git_blob_sha"]):
            raise ValueError(f"Invalid Git blob hash: {name}")
    if not seen:
        raise ValueError("Empty source lock")
    return lock


def verify(item, data):
    if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError(f"Source hash/size mismatch: {item['path']}")
    if "git_blob_sha" in item:
        blob_sha = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if blob_sha != item["git_blob_sha"]:
            raise ValueError(f"Git blob mismatch: {item['path']}")


def source_entries(lock):
    """Return C/header/build inputs used to compile the Linux module."""
    return [item for item in lock["files"] if not item["path"].endswith(".hex")]


def firmware_entries(lock):
    """Return the firmware/configuration files published beside the driver."""
    return [item for item in lock["files"] if item["path"].endswith(".hex")]


def all_entries(lock):
    """Return every hash-locked file, including firmware references."""
    return list(lock["files"])


def verify_vendor(lock, source=VENDOR):
    expected = {item["path"] for item in lock["files"]}
    actual = {path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()}
    if actual != expected or any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Vendored RDA tree differs from its complete file list")
    for item in lock["files"]:
        verify(item, (source / item["path"]).read_bytes())


def fetch(item, output, offline, *, vendor=VENDOR):
    output = output.resolve()
    target = output / item["path"]
    if not target.resolve().is_relative_to(output):
        raise ValueError(f"Source path escapes output directory: {item['path']}")
    if target.exists():
        verify(item, target.read_bytes())
        return
    if offline:
        raise FileNotFoundError(f"Missing source: {item['path']}")
    if vendor is not None:
        # A missing/corrupted bundled file is an error, never a silent network fallback.
        data = (vendor / item["path"]).read_bytes()
    else:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(item["url"], timeout=20) as response:
                    data = response.read(item["bytes"] + 1)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
    verify(item, data)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".work/rda-usb/source")
    parser.add_argument("--check-lock", action="store_true", help="Validate metadata only; no network")
    parser.add_argument("--verify-existing", action="store_true", help="Verify local files; no network")
    parser.add_argument("--source-only", action="store_true",
                        help="Fetch only the 48 driver/build files (legacy build mode)")
    parser.add_argument("--download-upstream", action="store_true",
                        help="Explicitly download locked upstream files instead of copying the bundled tree")
    args = parser.parse_args()
    if args.download_upstream and args.verify_existing:
        parser.error("--download-upstream and --verify-existing cannot be combined")
    lock = load_lock()
    entries = source_entries(lock) if args.source_only else all_entries(lock)
    if not args.download_upstream:
        verify_vendor(lock)
    if args.check_lock:
        print(f"Validated {len(lock['files'])} source/firmware references; "
              f"{len(source_entries(lock))} source files and {len(firmware_entries(lock))} firmware files available")
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        # Materialize results so every worker failure propagates to the caller.
        list(pool.map(lambda item: fetch(item, args.output, args.verify_existing,
                                        vendor=None if args.download_upstream else VENDOR), entries))
    kind = "driver source files" if args.source_only else "driver/firmware files"
    origin = "upstream download" if args.download_upstream else "bundled tree; no network"
    print(f"Verified {len(entries)} pinned {kind} from {origin}; no vendor code executed")


if __name__ == "__main__":
    main()
