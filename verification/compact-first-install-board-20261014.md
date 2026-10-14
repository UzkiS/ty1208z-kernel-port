# Compact RAM/web first installation

2026-10-14, TY1208Z CA / Hi3798MV100, eMMC `008G30`, 1 GiB physical DDR.

The user requested interruption of the full-p9 stream and a compact installer
using TTL plus Ethernet to enter temporary OpenWrt, followed by a web upload.
The old writer stopped after 5,149,818,880 bytes, flushed and relocked p9;
p6 was untouched. Its automatic continuation also stopped. That partial p9
was never treated as bootable.

The new private upload is 131,840,201 bytes (about 126 MiB), including a fixed
1-GiB ext4 root and a 4,471,812-byte disk-root uImage. It writes p9 first,
flushes and hashes its complete readback, restores the selected configuration,
then writes, reads back and locks p6. No bootloader, persistent boot setting,
other eMMC partition, SD, boot0/boot1 or RPMB write is part of the installer.
The installed root includes an APK for first-boot online growth to the full
6,846-MiB p9, and the separate file-level backend for subsequent native upgrades.

Measured checks so far:

- Fresh ext4 creation and `e2fsck`; bounded ARM archive/uImage/ext4 parser checks.
- Static ARM `resize2fs` expands the offline fixture to the full p9 size;
  filesystem checks pass afterward. This does not prove online growth.
- Real board official `sysupgrade --test` passes without storage writes.
  LuCI preflight hashes the compressed payload; full expanded geometry and SHA
  validation remains mandatory before either partition is unlocked.
- Real Chinese LuCI firmware upload and confirmation pass with the expected
  image SHA and configuration retention selected.
- The first actual stage2 attempt exposed a missing `tr` in its copied tools.
  It stopped before the write marker, and official `upgraded` rebooted despite
  the failing stage2 exit. UART intercepted that reboot. The identical accepted
  RAM system and configuration were recovered through CRC-verified TFTP.
- The addon now copies `tr`. Its failure path displays the log and keeps a
  serial recovery shell alive instead of returning to `upgraded`. Since official
  sysupgrade skips backups on tmpfs, the RAM-only pre-upgrade hook archives the
  official `--list-backup` selection when configuration retention is requested.
- The corrected real LuCI/sysupgrade run passes the RAM pivot and full
  expanded-root validation, and is writing the compact p9. Readback, persistent boot and online growth
  are still pending at this record's current checkpoint.

The same failed-stage2 return issue was corrected in the separate daily upgrade
backend. Its preflight now hashes the compressed archive within LuCI's RPC
timeout, retaining mandatory expanded path/space checks before stage2 mounts p9.
A new private package/image builds with the previously recorded exact compiler
and libc; physical disk-root preflight remains pending until installation ends.

Unchanged RAM, Ethernet, Chinese UI, Docker, Passwall cores, wireless and time64
evidence is reused. No application matrix was repeated. Private UART logs,
receipts, configuration archives and original RDA firmware remain local.
