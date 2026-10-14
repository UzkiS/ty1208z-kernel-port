# Official native web upgrade and persistent restart

2026-10-15, TY1208Z CA / Hi3798MV100, eMMC 008G30, single-core ARMv7.
Official OpenWrt 25.12 commit 58efa9917d4cc53fceed173529a286187649e827;
Linux 6.12.112. No computer-use or HiTool.

## Exact accepted daily image

131287242 B, SHA-256
d13100b476e386276846454f4985841d7fb89717d79202223c5b17ecc7483fd8.
Kernel 4560012 B, SHA-256
9c1ae8054e2e62251d10ee8cbef79287249bf69be5ab940a80441710408447d5;
ABI 6.12.112~3ff30746f86cc6101046198a6e9bf330-r1.
The build filename retains UNTESTED; this exact daily image has the following
physical acceptance. Original RDA firmware stays private.

## Physical upgrade acceptance

- Independent headless Chromium logged into official Chinese LuCI Backup/Flash,
  uploaded the exact image, matched its SHA-256 and selected keep configuration.
- Official sysupgrade stopped services and stage2 pivoted into RAM. UART shows
  the p9 root remount/unmount, subsequent staging mount and cold-readback cache drop.
- The file-level backend verified staged root files, activated managed directories,
  wrote/read back p6 and returned for the official default reboot.
- Receive-only COM9 captured CA loader, 1 GiB DDR, all eleven exact allocations,
  kernel start and default eMMC root boot; no UART command or boot setting change.
- Real ext4 rw p9 remains 1752576 x 4096 B, full 6846 MiB. p6/other partitions and
  SD remain read-only. Discard/WRITE_ZEROES queue limits are zero.
- Network/LuCI/Passwall/Docker/wireless/account/key hashes are unchanged. Native
  Docker startup appends an identical docker network list entry to firewall; after
  removing only repeated adjacent entries its bytes equal the saved original.
  Effective firewall settings are unchanged; duplicate entries are cleaned after
  the final reboot. The /root marker and retained Docker container content pass.
- Docker 29.6.1 autostarts with /opt/docker and the overlayfs snapshotter; the
  unchanged engine APK's pre-read/bounded respawn repair avoids cold containerd timeout.
- block-mount and lsblk are installed. The real official Chinese mount page renders
  UUID configuration and the current eMMC filesystem; no settings were saved.
- Normal startup records complete and removes the obsolete staging transaction.

## One ordinary persistent reboot

After upgrade acceptance, dockerd stopped and sync completed, then the ordinary
reboot command was issued once. MMC shutdown retained the mounted-root gendisk,
claimed an idle PIO host and disabled IRQs/clock without card writes. UART records
EMMC_RO_SHUTDOWN_COMPLETE host-retained clock-disabled no-card-writes, the accepted
SD shutdown and USB-host shutdown markers. Default autoboot follows with fresh
eleven-allocation evidence, kernel start and no panic/ext4 error. SSH returns with
the same configuration, full p9, automatic Docker engine and retained container data.
No manual power cycle or UART input was needed for this repaired reboot.

## Scope and remaining limits

Unchanged memory, Ethernet, proxy-core, wireless STA/AP, container feature and time64
evidence was reused. The new whole first-install image was not reflashed: its accepted
process and changed kernel/resize/application boundaries were reused. First installation
wrote 1 GiB p9 in about 29 minutes and read back in about 11; single-sector PIO remains.

The persistent kernel includes SCSI/BLK_DEV_SD/USB_STORAGE and existing ext4/VFAT/exFAT.
No external USB disk was plugged in at this earlier checkpoint. Later VFAT/NTFS3
physical acceptance and its newer image are recorded in the [USB report](usb-storage-board-20261015.md). SD remains request-level
read-only; writable SD/formatting and wireless-uplink bypass-routing are not accepted.
Wi-Fi stays disabled by default. CA fastboot, persistent boot settings, other eMMC
partitions, SD, boot0/boot1/RPMB and security state are preserved.

Private UART evidence hashes (raw logs are not published):

- Official upgrade UART: `1cb2026fb3fef7ac8088dab864c5f26f9936db9424654f1505100487a8c3bd19`.
- Ordinary reboot UART: `a3f986c2359836cc7298f2e95bc308f316aee09eb7501959d9487fd2ea319943`.
- Chinese mount view text: `b6ae70a1b09d2a6d9800d08dde7722bd593406b5bff0427169ca73d0a3803a28`.
