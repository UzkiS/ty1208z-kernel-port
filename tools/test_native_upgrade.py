#!/usr/bin/env python3
"""Exercise the actual parser on valid streams and unsafe/truncated uploads."""
import argparse
import gzip
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

from native_upgrade import PROJECT, digest


def tar(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, kind, data in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
            if kind == tarfile.SYMTYPE:
                member.linkname = data.decode()
                archive.addfile(member)
            elif kind == tarfile.DIRTYPE:
                archive.addfile(member)
            else:
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads((args.delivery / "manifest.json").read_bytes())
    image = args.delivery / receipt["image"]["file"]
    assert digest(image) == receipt["image"]["sha256"]
    source = PROJECT / "openwrt/system/upgrade/image-check.c"
    checked = []
    with tempfile.TemporaryDirectory(prefix="ty1208z-upgrade-parser-") as folder:
        work = Path(folder)
        checker = work / "image-check"
        subprocess.run(["cc", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        str(source), "-o", str(checker)], check=True)

        def check(label, arguments, data=None, valid=True):
            result = subprocess.run([str(checker), *arguments], input=data,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
            assert (result.returncode == 0) == valid, (label, result.stderr.decode())
            assert b"AddressSanitizer" not in result.stderr and b"runtime error:" not in result.stderr
            checked.append(label)
            return result.stdout

        check("actual-fwtool-image", ["outer", str(image)])
        kernel = check("actual-kernel-member", ["member", str(image), "kernel"])
        path = work / "kernel"
        path.write_bytes(kernel)
        check("actual-uimage-crc", ["kernel", str(path)])
        path.write_bytes(kernel[:-1] + bytes([kernel[-1] ^ 1]))
        check("corrupt-uimage", ["kernel", str(path)], valid=False)
        # Stream the real root through the ARM delivery's identical parser too.
        compressed = check("actual-root-member", ["member", str(image), "rootfs.tar.gz"])
        root = gzip.decompress(compressed)
        space = check("actual-safe-root", ["root"], root)
        assert int(space) == receipt["manifest"]["root_space"]
        check("actual-staged-root-readback", ["verify-root", str(args.delivery / "root")], root)
        arm = args.delivery / "root/sbin/ty1208z-image-check"
        result = subprocess.run(["qemu-arm", str(arm), "root"], input=root, capture_output=True, timeout=90)
        assert result.returncode == 0 and result.stdout == space, result.stderr.decode()
        checked.append("actual-ARM-root-parser")
        required = [(n, tarfile.DIRTYPE, b"") for n in ("bin", "etc", "lib", "lib/apk", "lib/apk/db", "lib/upgrade", "sbin", "usr", "var", "www")]
        required += [(n, tarfile.REGTYPE, b"ok") for n in (
            "bin/busybox", "sbin/procd", "lib/apk/db/installed", "etc/ty1208z-disk-root",
            "etc/ty1208z-upgrade-abi", "lib/upgrade/platform.sh", "sbin/ty1208z-image-check", "init")]
        check("minimal-valid-root", ["root"], tar(required))
        for label, extra in {
            "parent-traversal": [("etc/../opt/docker/layer", tarfile.REGTYPE, b"bad")],
            "absolute-path": [("/etc/shadow", tarfile.REGTYPE, b"bad")],
            "Docker-replacement": [("opt", tarfile.DIRTYPE, b"")],
            "symlink-parent": [("etc/link", tarfile.SYMTYPE, b"/opt/docker"),
                               ("etc/link/layer", tarfile.REGTYPE, b"bad")],
            "duplicate-path": [("etc/ty1208z-disk-root", tarfile.REGTYPE, b"bad")],
            "hardlink": [("etc/hardlink", tarfile.LNKTYPE, b"")],
        }.items():
            check(label, ["root"], tar(required + extra), valid=False)
        check("truncated-root", ["root"], tar(required)[:700], valid=False)
        staged = work / "staged"
        staged.mkdir()
        with tarfile.open(fileobj=io.BytesIO(tar(required))) as archive:
            archive.extractall(staged, filter="data")
        check("fixture-staged-readback", ["verify-root", str(staged)], tar(required))
        (staged / "bin/busybox").write_bytes(b"NO")
        check("corrupt-staged-readback", ["verify-root", str(staged)], tar(required), valid=False)
        path = work / "bad-outer"
        path.write_bytes(tar([("../kernel", tarfile.REGTYPE, b"bad")]))
        check("unexpected-outer-name", ["outer", str(path)], valid=False)
        path.write_bytes(bytes(1024))
        check("empty-outer", ["outer", str(path)], valid=False)
    output = {"status": "offline parser/ARM checks passed; not a physical upgrade acceptance",
              "checks": checked, "image_sha256": receipt["image"]["sha256"],
              "parser_sha256": digest(source)}
    (args.delivery / "parser-checks.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
