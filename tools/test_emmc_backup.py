#!/usr/bin/env python3
"""Exercise real streamed host backup acceptance, without a device or network."""
import argparse
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from backup_emmc_readonly import guard, stream
from backup_emmc_readonly import COMPATIBLE, LAYOUT

BUSYBOX = None


class BackupTests(unittest.TestCase):
    def process(self, data, code=0):
        return subprocess.Popen([sys.executable, "-c",
                                 "import sys; sys.stdout.buffer.write(bytes.fromhex(sys.argv[1])); sys.exit(int(sys.argv[2]))",
                                 data.hex(), str(code)], stdout=subprocess.PIPE)

    def test_complete_exact_stream_and_saved_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.partial"
            data = bytes(range(256)) * 32
            result = stream(self.process(data), path, len(data))
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(result["bytes"], len(data))
            self.assertEqual(len(result["sha256"]), 64)

    def test_short_extra_and_error_streams_never_pass(self):
        for data, code in ((b"short", 0), (b"too-long-data", 0), (b"12345678", 1)):
            with self.subTest(data=data, code=code), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    stream(self.process(data, code), Path(directory) / "backup.partial", 8)

    def test_exclusive_output_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing"
            path.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                stream(self.process(b"new"), path, 3)
            self.assertEqual(path.read_bytes(), b"existing")

    def test_saved_file_corruption_is_rejected(self):
        class Process:
            stdout = io.BytesIO(b"12345678")

            def wait(self, timeout=None):
                path.write_bytes(b"87654321")
                return 0

            def poll(self):
                return 0

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.partial"
            with self.assertRaisesRegex(ValueError, "differs"):
                stream(Process(), path, 8)

    def test_guard_requires_exact_fdt_and_has_no_card_output(self):
        with self.assertRaises(ValueError):
            guard("invalid")
        command = guard("a" * 64)
        self.assertIn("test \"$count\" = 10", command)
        self.assertIn('test "$(cat "$block/ro")" = 1', command)
        self.assertIn("1249280 14020608", command)
        self.assertNotIn("dd of=", command)

    def test_actual_arm_preflight_rejects_changed_state_before_streaming(self):
        if BUSYBOX is None:
            self.skipTest("Use --busybox for actual selected ARM shell validation")
        with tempfile.TemporaryDirectory(prefix="emmc-backup-guard-") as directory:
            root = Path(directory)
            def write(name, data):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data if isinstance(data, bytes) else data.encode())
            write("sys/firmware/devicetree/base/compatible", (COMPATIBLE + "\0hi3798mv100-series\0").encode())
            write("sys/firmware/fdt", b"synthetic-fdt")
            write("sys/class/block/mmcblk0/device/name", "008G30\n")
            write("sys/class/block/mmcblk0/size", "15269888\n")
            write("sys/class/block/mmcblk0/ro", "1\n")
            write("dev/mmcblk0", b"synthetic-block")
            for index, (start, size) in enumerate(LAYOUT, 1):
                for key, value in (("start", start), ("size", size), ("ro", 1)):
                    write(f"sys/class/block/mmcblk0p{index}/{key}", f"{value}\n")
            for name in ("mounts", "swaps", "self/mountinfo"):
                write("proc/" + name, "")
            script = guard(hashlib.sha256(b"synthetic-fdt").hexdigest())
            script = script.replace("/sys/", str(root / "sys") + "/").replace("/proc/", str(root / "proc") + "/")
            # Synthetic fixtures never open a real block node; only this type
            # check is replaced. All actual identity/hash/RO/layout checks run.
            script = script.replace("test -b /dev/mmcblk0", "test -f " + str(root / "dev/mmcblk0"))
            script = "uname() { echo 6.12.112; }\n" + script + "preflight\necho STREAM_ALLOWED\n"
            def run():
                return subprocess.run(["qemu-arm", str(BUSYBOX), "sh", "-s"], input=script,
                                      capture_output=True, text=True, timeout=10)
            accepted = run()
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(accepted.stdout, "STREAM_ALLOWED\n")
            for name, replacement in (("sys/class/block/mmcblk0/ro", "0\n"),
                                      ("sys/class/block/mmcblk0p9/ro", "0\n"),
                                      ("sys/class/block/mmcblk0p9/start", "1\n"),
                                      ("sys/class/block/mmcblk0/size", "1\n"),
                                      ("sys/class/block/mmcblk0/device/name", "foreign\n"),
                                      ("sys/firmware/fdt", "changed"),
                                      ("proc/mounts", "/dev/mmcblk0p9 /mnt ext4 ro 0 0\n"),
                                      ("proc/self/mountinfo", "25 1 179:9 / /mnt ro - ext4 /dev/root ro\n"),
                                      ("proc/swaps", "/dev/mmcblk0p9 partition 1 0 -1\n")):
                path = root / name
                original = path.read_bytes()
                write(name, replacement)
                refused = run()
                self.assertNotEqual(refused.returncode, 0, name)
                self.assertNotIn("STREAM_ALLOWED", refused.stdout, name)
                path.write_bytes(original)
            write("sys/class/block/mmcblk0boot0/ro", "1\n")
            self.assertNotEqual(run().returncode, 0)
            print("EMMC_RO_BACKUP_ARM_GUARD_PASS exact identity/hash/RO/layout/unmounted and suppressed-node gates; synthetic files only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--busybox", type=Path)
    args = parser.parse_args()
    BUSYBOX = args.busybox
    unittest.main(argv=[__file__], verbosity=2)
