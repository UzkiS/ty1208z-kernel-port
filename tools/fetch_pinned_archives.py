#!/usr/bin/env python3
"""Fetch fixed Linux/BusyBox archives atomically; retry transient transport only."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS = 3
SOCKET_TIMEOUT = 20
ATTEMPT_SECONDS = 180
MAX_BYTES = 512 * 1024 * 1024


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def transient(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 429, 500, 502, 503, 504}
    if isinstance(error, urllib.error.URLError):
        return not isinstance(error.reason, ssl.SSLCertVerificationError)
    return isinstance(error, (TimeoutError, ConnectionError, http.client.IncompleteRead))


def fetch(url, expected, archive):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
            not re.fullmatch(r"[0-9a-f]{64}", expected)):
        raise ValueError("Expected HTTPS and an exact SHA-256")
    if archive.exists():
        if sha256(archive) != expected:
            raise ValueError(f"Cached archive hash mismatch: {archive.name}")
        return
    archive.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(ATTEMPTS):
        temporary = None
        try:
            deadline = time.monotonic() + ATTEMPT_SECONDS
            with urllib.request.urlopen(url, timeout=SOCKET_TIMEOUT) as response:
                if urllib.parse.urlsplit(response.geturl()).scheme != "https":
                    raise ValueError("Archive redirect downgraded HTTPS")
                length = response.headers.get("Content-Length")
                length = int(length) if length is not None else None
                if length is not None and not 0 <= length <= MAX_BYTES:
                    raise ValueError("Archive exceeds download budget")
                digest = hashlib.sha256()
                count = 0
                with tempfile.NamedTemporaryFile(dir=archive.parent, prefix="." + archive.name + ".",
                                                 suffix=".part", delete=False) as stream:
                    temporary = Path(stream.name)
                    while True:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Archive download deadline exceeded")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        count += len(chunk)
                        if count > MAX_BYTES:
                            raise ValueError("Archive exceeds download budget")
                        digest.update(chunk)
                        stream.write(chunk)
                if length is not None and count != length:
                    raise http.client.IncompleteRead(b"", max(length - count, 0))
                if digest.hexdigest() != expected:
                    raise ValueError(f"Downloaded archive hash mismatch: {archive.name}")
            # No canonical archive is exposed until transfer and SHA both pass.
            os.replace(temporary, archive)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as error:
            if not transient(error) or attempt + 1 == ATTEMPTS:
                raise
            print(f"{archive.name}: transient download failure; retry {attempt + 2}/{ATTEMPTS}: {error}",
                  flush=True)
            time.sleep(attempt + 1)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taskbase", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((ROOT / "config/sources.lock.json").read_text())
    for kind in ("linux", "busybox"):
        item = lock[kind]
        name = urllib.parse.urlsplit(item["url"]).path.rsplit("/", 1)[-1]
        if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]+", name):
            raise ValueError("Invalid locked archive basename")
        fetch(item["url"], item["sha256"], args.taskbase / "downloads" / name)
        print(f"{kind}: pinned archive SHA256 verified", flush=True)


if __name__ == "__main__":
    main()
