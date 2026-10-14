#!/usr/bin/env python3
"""PTY integration: identity gates, failed reset and actual fresh loader inspection."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from bootloader_probe import BootloaderProbe
from openwrt_ethernet_board_cli import DT_IDENTITY, SOURCE_REVISION
from board_restart_cli import SD_DT_IDENTITY, SD_RO_RESTART_GUARD, RAM768_RESTART_GUARD, EMMC_RO_RESTART_GUARD

ROOT = Path(__file__).resolve().parents[1]


class RestartSerialTests(unittest.TestCase):
    def exercise(self, mode, profile="diagnostic"):
        with tempfile.TemporaryDirectory(prefix="restart-cli-") as directory:
            prefix = Path(directory) / "capture"
            master, slave = pty.openpty()
            errors = []
            sent = []
            native = profile in ("router", "router768", "router-sdro", "router-emmcro")
            sd_ident = profile in ("sd-ident1", "sd-ro1")
            sd_shutdown = sd_ident or profile == "router-sdro"
            memory = profile == "ram768"
            emmc_ro = profile in ("emmc-ro1", "router-emmcro")
            prompt = b"root@OpenWrt:~# " if native else b"# "

            def read_command():
                buffer = bytearray()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        buffer.extend(os.read(master, 1))
                        if buffer.endswith(b"\r") or buffer == b"\x03":
                            sent.append(bytes(buffer))
                            return bytes(buffer)
                raise AssertionError("No expected command")

            def peer():
                try:
                    self.assertEqual(read_command(), b"\r")
                    if mode == "bootloader":
                        os.write(master, b"\r\nfastboot# ")
                        return
                    os.write(master, b"\r\n" + prompt)
                    self.assertEqual(read_command(), b"uname -r\r")
                    release = (b"4.4.35_ecoo" if mode == "hinas" else b"6.12.112" if native else
                               b"6.12.112-ty1208z-" + profile.encode() if sd_ident or memory or emmc_ro else b"6.12.112-ty1208z-restart1")
                    os.write(master, b"uname -r\r\n" + release + b"\r\n" + prompt)
                    if mode == "hinas":
                        return
                    if native:
                        self.assertEqual(read_command(), b"cat /etc/openwrt_release\r")
                        revision = b"foreign" if mode == "source" else SOURCE_REVISION
                        os.write(master, b"DISTRIB_TARGET='hi3798mv100/apps'\r\nDISTRIB_REVISION='" + revision + b"'\r\n" + prompt)
                        if mode == "source":
                            return
                        self.assertEqual(read_command(), DT_IDENTITY + b"\r")
                        dt = (b"other,board" if mode == "dt" else
                              b"tianyi,ty1208z-ca-openwrt-emmcro-ram" if profile == "router-emmcro" else
                              b"tianyi,ty1208z-ca-openwrt-sdro-ram" if profile == "router-sdro" else
                              b"tianyi,ty1208z-ca-openwrt-router768-ram" if profile == "router768" else
                              b"tianyi,ty1208z-ca-openwrt-router-ram")
                        os.write(master, dt + b"\r\n" + prompt)
                        if mode == "dt":
                            return
                        if profile != "router-emmcro":
                            binding = read_command()
                            self.assertIn(b"readlink /sys/bus/platform/devices/", binding)
                            os.write(master, (b"unbound" if mode == "unbound" else b"../../../bus/platform/drivers/ty1208z-sp805-restart") + b"\r\n" + prompt)
                            if mode == "unbound":
                                return
                        if profile == "router-sdro":
                            self.assertEqual(read_command(), SD_RO_RESTART_GUARD + b"\r")
                            state = b"SD_RO_MOUNT_ACTIVE" if mode == "mounted" else b"SD_RO_RESTART_GUARD"
                            if mode == "writable":
                                state = b""
                            os.write(master, state + b"\r\n" + prompt)
                            if mode in {"mounted", "writable"}:
                                return
                            self.assertEqual(read_command(), RAM768_RESTART_GUARD + b"\r")
                            state = b"RAM768_MOUNT_ACTIVE" if mode == "memory-active" else b"RAM768_RESTART_GUARD"
                            os.write(master, state + b"\r\n" + prompt)
                            if mode == "memory-active":
                                return
                    if sd_ident:
                        self.assertEqual(read_command(), SD_DT_IDENTITY + b"\r")
                        board = b"sd-ro" if profile == "sd-ro1" else b"sd-ident"
                        dt = b"other,board" if mode == "dt" else b"tianyi,ty1208z-ca-" + board + b"-ram\x00hi3798mv100-series\x00"
                        os.write(master, dt + b"\r\n" + prompt)
                        if mode == "dt":
                            return
                        self.assertEqual(read_command(), b"readlink /sys/bus/platform/devices/f8a2c000.sd-restart/driver\r")
                        binding = b"unbound" if mode == "unbound" else b"../../../bus/platform/drivers/ty1208z-mv100-sd-restart"
                        os.write(master, binding + b"\r\n" + prompt)
                        if mode == "unbound":
                            return
                        if profile == "sd-ro1":
                            self.assertEqual(read_command(), SD_RO_RESTART_GUARD + b"\r")
                            os.write(master, (b"SD_RO_MOUNT_ACTIVE" if mode == "mounted" else b"SD_RO_RESTART_GUARD") + b"\r\n" + prompt)
                            if mode == "mounted":
                                return
                    if emmc_ro:
                        self.assertEqual(read_command(), SD_DT_IDENTITY + b"\r")
                        board = b"tianyi,ty1208z-ca-openwrt-emmcro-ram" if native else b"tianyi,ty1208z-ca-emmc-ro-ram"
                        identity = b"foreign" if mode == "dt" else board + b"\x00hi3798mv100-series\x00"
                        os.write(master, identity + b"\r\n" + prompt)
                        if mode == "dt":
                            return
                        self.assertEqual(read_command(), b"readlink /sys/bus/platform/devices/f8a2c000.emmc-ro-restart/driver\r")
                        binding = b"unbound" if mode == "unbound" else b"../../../bus/platform/drivers/ty1208z-mv100-emmc-ro-restart"
                        os.write(master, binding + b"\r\n" + prompt)
                        if mode == "unbound":
                            return
                        self.assertEqual(read_command(), EMMC_RO_RESTART_GUARD + b"\r")
                        state = b"EMMC_RO_MOUNT_ACTIVE" if mode in {"mounted", "cleanup"} else b"EMMC_RO_RESTART_GUARD"
                        if mode in {"writable", "capacity"}:
                            state = b""
                        os.write(master, state + b"\r\n" + prompt)
                        if mode in {"mounted", "cleanup", "writable", "capacity"}:
                            return
                    if memory:
                        self.assertEqual(read_command(), SD_DT_IDENTITY + b"\r")
                        identity = b"foreign" if mode == "dt" else b"tianyi,ty1208z-ca-ram768\x00hi3798mv100-series\x00"
                        os.write(master, identity + b"\r\n" + prompt)
                        if mode == "dt":
                            return
                        self.assertEqual(read_command(), b"readlink /sys/bus/platform/devices/f8a2c000.ram-restart/driver\r")
                        binding = b"unbound" if mode == "unbound" else b"../../../bus/platform/drivers/ty1208z-mv100-ram-restart"
                        os.write(master, binding + b"\r\n" + prompt)
                        if mode == "unbound":
                            return
                        self.assertEqual(read_command(), RAM768_RESTART_GUARD + b"\r")
                        os.write(master, (b"RAM768_MOUNT_ACTIVE" if mode == "mounted" else b"RAM768_RESTART_GUARD") + b"\r\n" + prompt)
                        if mode == "mounted":
                            return
                    report_command = b"dmesg | grep -E 'TY1208Z_(SYSTEM_)?RESTART_READY|TY1208Z_MV100_RESTART_READY'; echo TY1208Z_RESTART_CHECK_COMPLETE"
                    self.assertEqual(read_command(), report_command + b"\r")
                    registration = b"not registered" if mode == "missing" else (
                        b"[0.4] driver: TY1208Z_RESTART_READY no-startup-writes explicit-restart-only")
                    if (native or sd_ident or memory or emmc_ro) and mode != "missing-mv100":
                        registration += b"\r\n[0.5] driver: TY1208Z_MV100_RESTART_READY sysid=37980100 measured-inactive-watchdog no-startup-writes"
                    completion = (report_command if mode == "echo-completion"
                                  else b"TY1208Z_RESTART_CHECK_COMPLETE")
                    os.write(master, registration + b"\r\n" + completion + b"\r\n" + prompt)
                    if mode in {"missing", "echo-completion", "missing-mv100"}:
                        return
                    self.assertEqual(read_command(), b"reboot\r" if native else b"reboot -f\r")
                    if mode == "failed":
                        os.write(master, b"Reboot fai")
                        time.sleep(0.03)
                        os.write(master, b"led -- System halted\r\n")
                        return
                    if mode == "failed-shutdown":
                        tag = b"EMMC_RO" if emmc_ro else b"SD_IDENT"
                        os.write(master, b"[0.7] driver: " + tag + b"_SHUTDOWN_FAILED controller-not-quiesced\r\n")
                        return
                    if mode == "restart-refused":
                        os.write(master, b"EMMC_RO_RESTART_REFUSED controller-not-quiesced\r\n")
                        return
                    if sd_shutdown and mode != "missing-shutdown":
                        os.write(master, b"[0.7] driver: SD_IDENT_SHUTDOWN_COMPLETE host-removed clock-disabled no-card-writes\r\n")
                    if emmc_ro and mode != "missing-shutdown":
                        os.write(master, b"[0.7] driver: EMMC_RO_SHUTDOWN_COMPLETE host-removed clock-disabled no-card-writes\r\n")
                    os.write(master, b"Bootrom start\r\nFastboot 3.3.0-dirty (test)\r\n"
                             b"CPU: Hi3798Mv100 (CA)\r\nReserve Memory\r\n")
                    self.assertEqual(read_command(), b"\x03")
                    os.write(master, b"\r\nfastboot# ")
                    for command in BootloaderProbe.COMMANDS:
                        self.assertEqual(read_command(), command)
                        os.write(master, command + b"\r\nread-only reply\r\nfastboot# ")
                except BaseException as exc:
                    errors.append(exc)

            process = subprocess.Popen([
                sys.executable, "-u", str(ROOT / "tools/board_restart_cli.py"),
                "--port", os.ttyname(slave), "--output", str(prefix), "--timeout", "5",
                "--profile", profile,
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            thread = threading.Thread(target=peer, daemon=True)
            thread.start()
            try:
                output, _ = process.communicate(timeout=15)
                thread.join(timeout=9)
                self.assertFalse(thread.is_alive())
                if errors:
                    raise errors[0]
                self.assertEqual(process.returncode, 0 if mode == "success" else 1, output.decode())
                self.assertFalse(select.select([master], [], [], 0.05)[0], "Extra command")
                report = json.loads(prefix.with_suffix(".json").read_text())
                self.assertEqual(report["restart_sent"], mode in {"success", "failed", "missing-shutdown", "failed-shutdown", "restart-refused"})
                if mode == "success":
                    self.assertEqual(report["probe"]["completed_commands"], len(BootloaderProbe.COMMANDS))
                    self.assertEqual(report["status"], "restart-bootloader-verified")
                    if sd_shutdown:
                        self.assertTrue(report["sd_shutdown_verified"])
                    if emmc_ro:
                        self.assertTrue(report["emmc_shutdown_verified"])
                self.assertFalse(report["persistent_writes"])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                os.close(slave)

    def test_foreign_system_and_missing_registration_get_no_restart(self):
        for mode in ("bootloader", "hinas", "missing", "echo-completion"):
            with self.subTest(mode=mode):
                self.exercise(mode)

    def test_failed_reset_is_not_retried(self):
        self.exercise("failed")

    def test_fresh_bootloader_is_identified_and_inspected(self):
        self.exercise("success")

    def test_native_router_requires_source_dt_bound_module_and_measured_guard(self):
        for profile in ("router", "router768", "router-sdro", "router-emmcro"):
            for mode in ("source", "dt", "unbound", "missing-mv100"):
                with self.subTest(mode=mode, profile=profile):
                    self.exercise(mode, profile)

    def test_native_router_uses_graceful_reboot_and_inspects_the_fresh_loader(self):
        self.exercise("success", "router")
        self.exercise("success", "router768")

    def test_sd_identification_requires_exact_dt_binding_guard_and_actual_shutdown(self):
        for mode in ("dt", "unbound", "missing-mv100", "missing-shutdown", "failed-shutdown", "failed", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode, "sd-ident1")

    def test_sd_read_only_requires_unmounted_state_and_matching_restart_profile(self):
        for mode in ("dt", "unbound", "mounted", "missing-mv100", "missing-shutdown", "failed-shutdown", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode, "sd-ro1")

    def test_memory_profile_requires_binding_completed_cleanup_and_measured_guard(self):
        for mode in ("dt", "unbound", "mounted", "missing-mv100", "failed", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode, "ram768")

    def test_native_sd_requires_read_only_unmounted_cleanup_and_actual_shutdown(self):
        for mode in ("mounted", "writable", "memory-active", "missing-shutdown", "failed-shutdown", "failed", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode, "router-sdro")

    def test_emmc_ro_requires_exact_identity_binding_capacity_cleanup_and_shutdown(self):
        for mode in ("dt", "unbound", "mounted", "cleanup", "writable", "capacity", "missing-mv100",
                     "missing-shutdown", "failed-shutdown", "restart-refused", "failed", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode, "emmc-ro1")

    def test_native_emmc_requires_embedded_binding_unmounted_state_and_shutdown(self):
        for mode in ("mounted", "cleanup", "writable", "capacity", "missing-shutdown",
                     "failed-shutdown", "restart-refused", "failed", "success"):
            with self.subTest(mode=mode):
                self.exercise(mode, "router-emmcro")


if __name__ == "__main__":
    unittest.main(verbosity=2)
