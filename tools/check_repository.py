#!/usr/bin/env python3
"""Check source hygiene and fixed inputs without downloading or device access."""
import ast
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
skip = {".git", ".work", "artifacts", "evidence", "__pycache__", ".ruff_cache"}
lock = json.loads((root / "config/sources.lock.json").read_text(encoding="utf-8"))
for kind in ("linux", "busybox"):
    assert lock[kind]["url"].startswith("https://")
    assert re.fullmatch(r"[0-9a-f]{64}", lock[kind]["sha256"])
for path in root.rglob("*"):
    rel = path.relative_to(root)
    if not path.is_file() or skip.intersection(rel.parts) or rel.parts[:2] == ("reference", "sdk"):
        continue
    if path.suffix not in {".py", ".sh", ".ps1", ".c", ".h", ".dts", ".json", ".yaml", ".yml", ".md", ".toml"} and path.name not in {"Makefile", "init", "diag"}:
        continue
    blob = path.read_bytes()
    text = blob.decode("utf-8")
    assert b"\r" not in blob, f"Use LF: {rel}"
    assert text.endswith("\n"), f"Missing final newline: {rel}"
    assert all(line == line.rstrip() for line in text.splitlines()), f"Trailing whitespace: {rel}"
    if path.suffix == ".py":
        ast.parse(text, filename=str(rel))
    if path.suffix == ".sh" or path.name in {"init", "diag"}:
        subprocess.run(["bash", "-n", str(path)], check=True)
    if path.suffix == ".json":
        json.loads(text)

workflow = (root / ".github/workflows/diagnostic.yml").read_text()
for action in re.findall(r"uses:\s*([^\s#]+)", workflow):
    assert re.fullmatch(r"[\w/-]+@[0-9a-f]{40}", action), f"Unpinned CI action: {action}"
assert "contents: read" in workflow
assert "persist-credentials: false" in workflow
print("Repository checks passed: source syntax, UTF-8/LF, fixed archive hashes, pinned read-only CI")
