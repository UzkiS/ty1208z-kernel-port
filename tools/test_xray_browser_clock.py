#!/usr/bin/env python3
"""Run the actual Xray browser generators with a synthetic clock and CPU seed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = r'''
package utils

import (
    "os"
    "strconv"
    "testing"
    "time"
    "math/rand"
)
func browserTestNow() time.Time {
    seconds, err := strconv.ParseInt(os.Getenv("XRAY_TEST_UNIX"), 10, 64)
    if err != nil { panic(err) }
    return time.Unix(seconds, 0).UTC()
}
func TestBrowserClock(t *testing.T) {
    if AnchoredChromeVersion < 144 || ChromeUACH == "" || MSEdgeUACH == "" {
        t.Fatal("package initialization published an invalid browser version/header")
    }
    for seed := int64(0); seed < 256; seed++ {
        globalRng = rand.New(rand.NewSource(seed))
        version := ChromeVersion()
        if version < 144 { t.Fatalf("seed=%d Chrome version=%d", seed, version) }
        for _, fork := range []string{"chrome", "edge", ""} {
            if getGreasedChUa(version, fork) == "" { t.Fatal("empty client-hint header") }
        }
        if SafariVersion() == "" { t.Fatal("empty Safari version") }
        day := browserTestNow().Unix()/86400
        start := time.Date(2026,1,13,0,0,0,0,time.UTC).Unix()/86400
        if day < start && version != 144 { t.Fatal("past clock did not retain the baseline") }
        if day > start+3650 && version <= 144 { t.Fatal("future version growth was lost") }
    }
}
'''


def execute(browser, go, directory, *, expect_failure=False):
    # Keep the actual generators and package initialization. Only the clock
    # and unavailable CPU-information dependency are deterministic seams.
    text = browser.decode()
    start = text.index("func GetRandomizer()")
    end = text.index("var globalRng", start)
    text = (text[:start] + "func GetRandomizer() *rand.Rand { return rand.New(rand.NewSource(1)) }\n\n" +
            text[end:])
    for dependency in ('\t"hash/fnv"\n', '\t"github.com/klauspost/cpuid/v2"\n'):
        if text.count(dependency) != 1:
            raise ValueError("Xray browser dependency seam changed")
        text = text.replace(dependency, "")
    if text.count("time.Now()") != 4:
        raise ValueError("Xray browser clock seam changed")
    (directory / "browser.go").write_text(text.replace("time.Now()", "browserTestNow()"))
    (directory / "clock_test.go").write_text(FIXTURE)
    (directory / "go.mod").write_text("module ty1208z-xray-browser-test\n\ngo 1.27\n")
    environment = {**os.environ, "GOTOOLCHAIN": "local", "GOWORK": "off", "GOPROXY": "off",
                   "GOOS": "linux", "GOARCH": "amd64", "CGO_ENABLED": "0"}
    for seconds in ((0,) if expect_failure else (-86400, 0, 1791676800, 2208988800, 253402300799)):
        result = subprocess.run([str(go), "test", "-count=1", "-v", "."], cwd=directory,
                                env={**environment, "XRAY_TEST_UNIX": str(seconds)},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        if expect_failure:
            if result.returncode == 0 or b"index out of range" not in result.stdout:
                raise ValueError("Original browser did not reproduce the startup index panic")
        elif result.returncode:
            raise ValueError(result.stdout.decode())


def run(source, go, archive=None):
    lock = json.loads((ROOT / "openwrt/applications/sources.lock.json").read_text())
    item, = lock["source_patches"]
    patched = source / item["source_file"]
    data = patched.read_bytes()
    if hashlib.sha256(data).hexdigest() != item["patched_sha256"]:
        raise ValueError("Actual Xray browser source differs from the locked patch")
    with tempfile.TemporaryDirectory(prefix="xray-browser-") as temporary:
        directory = Path(temporary)
        if archive is not None:
            if hashlib.sha256(archive.read_bytes()).hexdigest() != item["source_sha256"]:
                raise ValueError("Xray original source archive identity differs")
            with tarfile.open(archive) as upstream:
                original = upstream.extractfile(item["source_root"] + "/" + item["source_file"]).read()
            if hashlib.sha256(original).hexdigest() != item["original_sha256"]:
                raise ValueError("Xray original browser identity differs")
            execute(original, go, directory, expect_failure=True)
        execute(data, go, directory)
    print("XRAY_BROWSER_CLOCK_PASS: actual generators/init, 256 CPU seeds, 1969/1970/2026/2040/9999")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--go", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    run(args.source, args.go, args.archive)
