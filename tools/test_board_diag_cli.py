#!/usr/bin/env python3
"""Verify diagnostic-shell identity gates and bounded capture on Linux PTYs."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith("linux"), "PTY integration runs on Linux")
class DiagnosticTests(unittest.TestCase):
    def exercise(self, mode, profile="diag1"):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "capture"
            master, slave = os.openpty()
            errors = []
            commands = []

            def read_command():
                incoming = bytearray()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.05)[0]:
                        data = os.read(master, 1)
                        incoming.extend(data)
                        if data == b"\r":
                            commands.append(bytes(incoming))
                            return bytes(incoming)
                raise AssertionError("No command received")

            def peer():
                try:
                    self.assertEqual(read_command(), b"\r")
                    if mode == "bootloader":
                        os.write(master, b"\r\nfastboot# ")
                        return
                    os.write(master, b"\r\n# ")
                    self.assertEqual(read_command(), b"uname -r\r")
                    kernel = b"4.4.35" if mode == "wrong-kernel" else b"6.12.112-ty1208z-" + profile.encode()
                    os.write(master, b"uname -r\r\n" + kernel + b"\r\n# ")
                    if mode == "wrong-kernel":
                        return
                    diagnostic = b"usb-diag; diag" if profile == "usb-host1" else b"diag"
                    self.assertEqual(read_command(), diagnostic + b"; echo TY1208Z_DIAG_COMPLETE\r")
                    time64 = b"TIME64_FAIL" if mode == "probe-failure" else b"TIME64_PASS sizeof(time_t)=8 file=2208988800"
                    audit = b"EMMC_AUDIT_READ_ONLY_COMPLETE" if mode != "missing-audit" else b"No audit driver"
                    sd = b"No SD audit" if mode == "missing-sd" else (
                        b"SD_AUDIT CRG39=00042103\r\nSD_AUDIT LDO=00000060\r\n"
                        b"SD_AUDIT_CONTROLLER_READ_COMPLETE\r\n"
                        b"SD_AUDIT_READ_ONLY_COMPLETE no-card-commands no-control-writes")
                    if mode == "inactive-sd":
                        sd = sd.replace(b"SD_AUDIT_CONTROLLER_READ_COMPLETE",
                                        b"SD_AUDIT_CONTROLLER_SKIPPED inactive-clock-or-reset")
                    ident = b"No card" if mode == "missing-ident" else (
                        b"EMMC_IDENT_GUARD_PASS\r\nUsing PIO mode.\r\nnew MMC card\r\n"
                        b"name=008G30\r\ntype=MMC\r\nBLOCK_DISABLED\r\n"
                        b"EMMC_IDENT_COMPLETE sectors=15269888 bytes=7818182656")
                    samples = b"No samples" if mode == "missing-samples" else (
                        b"EMMC_SAMPLE_HINAS_HEADER_MATCH crc32=2ba1a125\r\n"
                        b"EMMC_SAMPLE_EXT4 magic=ef53 block_size=4096\r\n"
                        b"EMMC_SAMPLE_READ_COMPLETE count=4 no-block-device")
                    ethernet = b"No Ethernet audit" if mode == "missing-ethernet" else (
                        b"ETH_AUDIT CRG51=0000000b\r\nETH_AUDIT PHY_CRG=00000001\r\n"
                        b"ETH_AUDIT PHY_SELECT=00000000\r\nETH_AUDIT PHY_ADDRESS=00000001\r\n"
                        b"ETH_AUDIT PHY_LDO=00000068\r\n"
                        b"ETH_AUDIT_COMPLETE no-phy-writes no-clock-reset-writes no-dma")
                    clock_id = (
                        b"ETH_CLOCK_ID_FAILED error=-5" if mode == "failed-clock-id" else
                        b"ETH_CLOCK_ID_STATE before=00000003 enabled=0000000b restored=00000003 changed=1 verified=1\r\n"
                        b"ETH_CLOCK_ID_PHY_ID=20669901 addr=1\r\n"
                        b"ETH_CLOCK_ID_COMPLETE clock-restored no-phy-reset-writes no-dma")
                    network = b"No network driver" if mode == "missing-network" else (
                        b"ETH_NET_CLOCK_ENABLED crg51=0000000b inherited-phy\r\n"
                        b"ETH_NET_PHY_VERIFIED id=20669823 inherited-no-reset\r\n"
                        b"phy_id=0x20669823, phy_mode=mii")
                    usb = b"No USB audit" if mode == "missing-usb" else (
                        b"USB_AUDIT CRG46=0000007f CRG47=00000003\r\n"
                        b"USB_AUDIT USB0=00000008 USB1=0000b01c SYSID0=37980110\r\n"
                        b"USB_AUDIT_READ_ONLY_COMPLETE no-clock-reset-writes no-device-transactions")
                    restart = b"No restart handler" if mode == "missing-restart" else (
                        b"TY1208Z_RESTART_OBSERVED pid=00141805 cid=b105f00d control=00000000\r\n"
                        b"TY1208Z_RESTART_READY no-startup-writes explicit-restart-only")
                    usb_clock = b"USB_CLOCK_AUDIT_FAILED error=-5" if mode == "failed-usb-clock" else (
                        b"USB_CLOCK_AUDIT_BEFORE CRG46=0013707f CRG47=00000b01 USB0=000c71a8 USB1=00000000 SYSID0=37980100 changed=1\r\n"
                        b"USB_CLOCK_AUDIT_CAPS EHCI_CAPBASE=01000010 HCSPARAMS=00000012 HCCPARAMS=00000080 OHCI_REVISION=00000010\r\n"
                        b"USB_CLOCK_AUDIT_STOP CRG46=0010000e CRG47=00000f03 USB0=000c71a8 USB1=0000a801 error=0\r\n"
                        b"USB_CLOCK_AUDIT_COMPLETE sdk-last-user-stop no-device-transactions no-dma no-firmware")
                    if mode == "bad-usb-clock-stop":
                        usb_clock = usb_clock.replace(b"USB1=0000a801 error=0", b"USB1=0000a801 error=-5")
                    if mode == "missing-usb-clock-caps":
                        usb_clock = usb_clock.replace(b"USB_CLOCK_AUDIT_CAPS", b"CAPABILITIES_SKIPPED")
                    usb_host = (
                        b"USB_HOST0_PREPARED sdk-host0-sequence\r\n"
                        b"f9890000.usb driver=../../../bus/platform/drivers/ehci-platform\r\n"
                        b"f9880000.usb driver=../../../bus/platform/drivers/ohci-platform\r\n"
                        b"USB_HOST0_OBSERVATION ehci_root=1 ohci_root=1 rda=1\r\n"
                        b"USB_HOST0_OBSERVATION_COMPLETE no-class-driver no-firmware-loading")
                    if mode == "missing-usb-root":
                        usb_host = usb_host.replace(b"ohci_root=1", b"ohci_root=0")
                    if mode == "unbound-usb-host":
                        usb_host = usb_host.replace(b"driver=../../../bus/platform/drivers/ehci-platform", b"driver=unbound")
                    if mode == "failed-usb-host":
                        usb_host += b"\r\nUSB_HOST0_SHUTDOWN_READBACK_FAILED"
                    if mode == "no-rda":
                        usb_host = usb_host.replace(b"rda=1", b"rda=0")
                    # Fragment the output to exercise prompt/marker reassembly.
                    for part in (b"diag; echo TY1208Z_DIAG_COMPLETE\r\n", time64,
                                 b"\r\ndiagnostic output\r\n" * 1024,
                                 b"\r\n" + (audit if profile == "emmc-audit1" else b""),
                                 b"\r\n" + (sd if profile == "sd-audit1" else b""),
                                 b"\r\n" + (ident if profile in ("emmc-ident1", "emmc-read1") else b""),
                                 b"\r\n" + (samples if profile == "emmc-read1" else b""),
                                 b"\r\n" + (ethernet if profile == "ethernet-audit1" else b""),
                                 b"\r\n" + (clock_id if profile == "ethernet-clock-id1" else b""),
                                 b"\r\n" + (network if profile == "ethernet-net1" else b""),
                                 b"\r\n" + (usb if profile == "usb-audit1" else b""),
                                 b"\r\n" + (restart if profile == "restart1" else b""),
                                 b"\r\n" + (usb_clock if profile == "usb-clock-audit1" else b""),
                                 b"\r\n" + (usb_host if profile == "usb-host1" else b""),
                                 b"\r\nTY1208Z_DIAG_", b"COMPLETE\r\n# "):
                        os.write(master, part)
                        time.sleep(0.01)
                except BaseException as exc:
                    errors.append(exc)

            process = subprocess.Popen([
                sys.executable, "-u", str(ROOT / "tools/board_diag_cli.py"),
                "--port", os.ttyname(slave), "--output", str(prefix),
                "--profile", profile,
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                output, _ = process.communicate(timeout=15)
                thread.join(timeout=8)
                self.assertFalse(thread.is_alive())
                if errors:
                    raise errors[0]
                self.assertFalse(select.select([master], [], [], 0.05)[0], "Unexpected extra command")
                self.assertEqual(process.returncode, 0 if mode in ("success", "no-rda", "inactive-sd") else 1, output.decode())
                report = json.loads(prefix.with_suffix(".json").read_text())
                self.assertEqual(report["report_complete"], mode in ("success", "no-rda", "inactive-sd"))
                self.assertEqual(len(commands), 1 if mode == "bootloader" else 2 if mode == "wrong-kernel" else 3)
                if mode == "success":
                    self.assertIn(b"file=2208988800", prefix.with_suffix(".rx").read_bytes())
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                thread.join(timeout=8)
                os.close(master)
                os.close(slave)

    def test_bootloader_prompt_sends_no_shell_commands(self):
        self.exercise("bootloader")

    def test_wrong_kernel_sends_no_diagnostic_command(self):
        self.exercise("wrong-kernel")

    def test_probe_failure_is_not_success(self):
        self.exercise("probe-failure")

    def test_complete_fragmented_report_is_captured(self):
        self.exercise("success")

    def test_emmc_profile_requires_audit_completion(self):
        self.exercise("missing-audit", profile="emmc-audit1")

    def test_emmc_profile_captures_completed_audit(self):
        self.exercise("success", profile="emmc-audit1")

    def test_sd_register_audit_requires_real_completion_and_controller_disposition(self):
        self.exercise("missing-sd", profile="sd-audit1")
        self.exercise("success", profile="sd-audit1")
        self.exercise("inactive-sd", profile="sd-audit1")

    def test_identification_requires_card_and_capacity(self):
        self.exercise("missing-ident", profile="emmc-ident1")

    def test_identification_captures_card_and_capacity(self):
        self.exercise("success", profile="emmc-ident1")

    def test_sector_reads_require_content_checks(self):
        self.exercise("missing-samples", profile="emmc-read1")

    def test_sector_reads_capture_verified_content(self):
        self.exercise("success", profile="emmc-read1")

    def test_ethernet_audit_requires_control_state_and_completion(self):
        self.exercise("missing-ethernet", profile="ethernet-audit1")

    def test_ethernet_audit_captures_measured_state(self):
        self.exercise("success", profile="ethernet-audit1")

    def test_clock_id_requires_restoration_and_phy_id(self):
        self.exercise("failed-clock-id", profile="ethernet-clock-id1")

    def test_clock_id_captures_restored_clock_and_phy_id(self):
        self.exercise("success", profile="ethernet-clock-id1")

    def test_network_requires_bound_phy_and_mac(self):
        self.exercise("missing-network", profile="ethernet-net1")

    def test_network_binding_report_is_captured(self):
        self.exercise("success", profile="ethernet-net1")

    def test_usb_audit_requires_control_state_and_completion(self):
        self.exercise("missing-usb", profile="usb-audit1")

    def test_usb_read_only_report_is_captured(self):
        self.exercise("success", profile="usb-audit1")

    def test_restart_requires_actual_identity_and_registration(self):
        self.exercise("missing-restart", profile="restart1")

    def test_restart_read_only_report_is_captured(self):
        self.exercise("success", profile="restart1")

    def test_usb_clock_failure_is_not_accepted(self):
        self.exercise("failed-usb-clock", profile="usb-clock-audit1")

    def test_usb_clock_capabilities_and_shutdown_are_captured(self):
        self.exercise("success", profile="usb-clock-audit1")

    def test_usb_clock_failed_shutdown_is_not_accepted(self):
        self.exercise("bad-usb-clock-stop", profile="usb-clock-audit1")

    def test_usb_clock_missing_capabilities_are_not_accepted(self):
        self.exercise("missing-usb-clock-caps", profile="usb-clock-audit1")

    def test_usb_host_controllers_and_root_hubs_are_captured(self):
        self.exercise("success", profile="usb-host1")

    def test_usb_host_missing_root_hub_is_rejected(self):
        self.exercise("missing-usb-root", profile="usb-host1")

    def test_usb_host_unbound_controller_is_rejected(self):
        self.exercise("unbound-usb-host", profile="usb-host1")

    def test_usb_host_shutdown_failure_is_rejected(self):
        self.exercise("failed-usb-host", profile="usb-host1")

    def test_usb_host_controller_acceptance_does_not_invent_rda(self):
        self.exercise("no-rda", profile="usb-host1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
