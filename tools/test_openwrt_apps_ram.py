#!/usr/bin/env python3
"""Actual application DT/provenance mutations and two-CRC UART boot gates."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zlib

from inspect_images import parse_fdt
from openwrt_apps_ram_profile import (
    BOOTLOADER_BOUND_ADDRESS, INITRD_ADDRESS, LANGUAGE_MARKER, MAX_COMPRESSED,
    applications_ram_profile, validate_pair,
)
from prepare_ram_boot import prepare
from ram_boot_cli import load_image
from ymodem_sender import TransferError

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/openwrt-apps-ram1"
INSPECTION = (b"Fastboot 3.3.0-dirty (vendor)\r\n"
              b"DDR free region baseaddr:0x1000000 size:0x3F000000\r\n"
              b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0\r\n"
              b"loady [ off ] [ baud ]\r\ncrc32 address count [addr]\r\n"
              b"bootm [addr [arg ...]]\r\n")


def write_inspection(directory):
    (directory / "inspection.rx").write_bytes(INSPECTION)
    path = directory / "inspection.json"
    path.write_text(json.dumps({"stop_reason": "probe-complete", "raw_file": "inspection.rx",
                               "raw_sha256": hashlib.sha256(INSPECTION).hexdigest()}))
    return path


class ApplicationProfileTests(unittest.TestCase):
    def setUp(self):
        self.tree = parse_fdt((ARTIFACTS / "ty1208z-diagnostic.dtb").read_bytes())
        self.config = (ARTIFACTS / "linux.config").read_text()

    def test_actual_candidate_and_separate_range(self):
        data, _ = validate_pair(ARTIFACTS)
        with tempfile.TemporaryDirectory() as directory:
            plan = prepare(ARTIFACTS, write_inspection(Path(directory)))
        self.assertEqual(plan["additional_loads"][0]["address"], INITRD_ADDRESS)
        self.assertEqual(plan["additional_loads"][0]["bytes"], len(data))
        self.assertEqual(plan["additional_loads"][0]["image_crc32"], f"{zlib.crc32(data):08x}")
        self.assertLess(INITRD_ADDRESS + MAX_COMPRESSED, BOOTLOADER_BOUND_ADDRESS)
        self.assertGreater(INITRD_ADDRESS, plan["header_address"] + plan["image_bytes"] + 0x100000)

    def test_initrd_and_resource_mutations_are_rejected(self):
        for path, property_name in (("/chosen", "linux,initrd-start"), ("/chosen", "linux,initrd-end"),
                                    ("/memory@0", "reg"), ("/soc/serial@f8b00000", "reg")):
            tree = copy.deepcopy(self.tree)
            node = next(node for node in tree["nodes"] if node["path"] == path)
            node["properties"][property_name]["cells"][0] ^= 1
            with self.subTest(path=path, property=property_name), self.assertRaises(ValueError):
                applications_ram_profile(tree, self.config, ARTIFACTS)
        router = any(node["path"] == "/soc/ethernet@f9840000" for node in self.tree["nodes"])
        options = {"BLOCK", "MMC", "USB_SUPPORT", "SMP", "INITRAMFS_FORCE"}
        if not router:
            options.add("HISI_FEMAC")
        for option in options:
            with self.subTest(option=option), self.assertRaises(ValueError):
                applications_ram_profile(self.tree, self.config + f"CONFIG_{option}=y\n", ARTIFACTS)
        if router:
            for node in self.tree["nodes"]:
                if node["path"] not in {"/soc/clock-controller@f8a220cc", "/soc/mdio@f9841100",
                                        "/soc/mdio@f9841100/ethernet-phy@1", "/soc/ethernet@f9840000"}:
                    continue
                for key in node["properties"]:
                    tree = copy.deepcopy(self.tree)
                    changed = next(item for item in tree["nodes"] if item["path"] == node["path"])
                    value = changed["properties"][key]
                    # Zero-valued cells also decode as empty FDT strings.
                    # Mutate the type used by the actual resource policy.
                    kind = "strings" if key in {"compatible", "phy-mode"} else "cells"
                    value[kind] = ["changed"] if kind == "strings" else [0xdeadbeef]
                    with self.subTest(path=node["path"], property=key), self.assertRaises(ValueError):
                        applications_ram_profile(tree, self.config, ARTIFACTS)
            with self.assertRaises(ValueError):
                applications_ram_profile(self.tree, self.config.replace("CONFIG_HISI_FEMAC=y\n", ""), ARTIFACTS)
        tree = copy.deepcopy(self.tree)
        next(node for node in tree["nodes"] if node["path"] == "/")["properties"]["compatible"]["strings"][0] = "other,board"
        with self.assertRaises(ValueError):
            applications_ram_profile(tree, self.config, ARTIFACTS)

    def test_missing_memory_acceptance_or_mismatched_payload_is_rejected(self):
        report = json.loads((ARTIFACTS / "checks/applications-qemu-256.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "checks").mkdir()
            record = root / "checks/applications-qemu-256.json"
            changed = copy.deepcopy(report)
            changed["memory_limit_mib"] = 512
            record.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "bounded-memory"):
                validate_pair(root)
            for marker in report["passed_markers"]:
                if marker == LANGUAGE_MARKER:
                    continue  # Earlier measured images predate language acceptance.
                changed = copy.deepcopy(report)
                changed["passed_markers"].remove(marker)
                record.write_text(json.dumps(changed))
                with self.subTest(missing_marker=marker), self.assertRaisesRegex(ValueError, "bounded-memory"):
                    validate_pair(root)
            record.write_text(json.dumps(report))
            (root / "zImage").write_bytes(b"wrong kernel")
            with self.assertRaisesRegex(ValueError, "identity differs: kernel"):
                validate_pair(root)

    def test_language_marker_requires_actual_evidence_and_allows_earlier_images(self):
        report = json.loads((ARTIFACTS / "checks/applications-qemu-256.json").read_text())
        if LANGUAGE_MARKER not in report["passed_markers"]:
            self.skipTest("The measured historical image predates Chinese defaults")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "candidate"
            shutil.copytree(ARTIFACTS, root)
            record = root / "checks/applications-qemu-256.json"
            historical = copy.deepcopy(report)
            historical["passed_markers"].remove(LANGUAGE_MARKER)
            record.write_text(json.dumps(historical))
            validate_pair(root)
            console = root / "checks/qemu-applications-256.log"
            data = console.read_bytes().replace(LANGUAGE_MARKER.encode(), b"LANGUAGE_EVIDENCE_REMOVED")
            console.write_bytes(data)
            report["artifacts"]["console"] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            record.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "markers are absent"):
                validate_pair(root)

    def test_unapproved_transfer_address_or_command_sends_nothing(self):
        class NoCommands:
            def write(self, data):
                raise AssertionError("A load command was sent")
        for plan in ({"address": 0x8000, "load_command": "loady 8000 115200"},
                     {"address": INITRD_ADDRESS, "load_command": "nand write"}):
            with self.subTest(plan=plan), self.assertRaises(TransferError):
                load_image(NoCommands(), plan, b"payload")


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration runs on Linux")
class ApplicationBootGateTests(unittest.TestCase):
    def exercise(self, wrong):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inspection = write_inspection(root)
            plan = prepare(ARTIFACTS, inspection)
            master, slave = os.openpty()
            errors, boots = [], []

            def read_command():
                data = bytearray()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        data.extend(os.read(master, 1))
                        if data.endswith(b"\r"):
                            return bytes(data)
                raise AssertionError("No expected command")

            def peer():
                try:
                    for command, reply in (
                            (b"\r", b""), (b"version\r", b"Fastboot 3.3.0-dirty (vendor)"),
                            (b"getinfo ddrfree\r", b"DDR free region baseaddr:0x1000000 size:0x3F000000"),
                            (b"printenv bootcmd\r", b"bootcmd=mmc read 0 0x1FFFFC0 0x7000 0xA000;bootm 0x1FFFFC0")):
                        self.assertEqual(read_command(), command)
                        os.write(master, b"\r\n" + reply + b"\r\nfastboot# ")
                    for index, item in enumerate((plan, *plan["additional_loads"])):
                        self.assertEqual(read_command(), item["crc_command"].encode() + b"\r")
                        checksum = "00000000" if wrong == index else item["image_crc32"]
                        os.write(master, f"\r\nCRC32 for RAM ==> {checksum}\r\nfastboot# ".encode())
                        if wrong == index:
                            return
                    boots.append(read_command())
                    os.write(master, b"\r\nStarting kernel ...\r\nEXTERNAL_INITRD_PTY_CAPTURE\r\n")
                except BaseException as exc:
                    errors.append(exc)

            prefix = root / "capture"
            process = subprocess.Popen([
                sys.executable, "-u", str(ROOT / "tools/ram_boot_cli.py"), "--port", os.ttyname(slave),
                "--artifacts", str(ARTIFACTS), "--inspection", str(inspection), "--boot-existing",
                "--capture-seconds", "1", "--output", str(prefix),
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                output, _ = process.communicate(timeout=20)
                thread.join(timeout=8)
                self.assertFalse(thread.is_alive())
                if errors:
                    raise errors[0]
                self.assertEqual(process.returncode, 0 if wrong is None else 1, output.decode())
                result = json.loads(prefix.with_suffix(".json").read_text())
                self.assertEqual(result["ram_crc_verified"], wrong is None)
                self.assertEqual(result["boot_sent"], wrong is None)
                self.assertEqual(boots, [b"bootm 1ffffc0\r"] if wrong is None else [])
                self.assertFalse(select.select([master], [], [], 0.05)[0], "Extra command")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                os.close(slave)

    def test_each_payload_crc_gates_boot(self):
        for wrong in (0, 1, None):
            with self.subTest(wrong=wrong):
                self.exercise(wrong)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=ARTIFACTS)
    args = parser.parse_args()
    ARTIFACTS = args.artifacts.resolve()
    if not ARTIFACTS.is_dir():
        raise ValueError("Build the actual application RAM candidate before these tests")
    unittest.main(argv=[__file__], verbosity=2)
