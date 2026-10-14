# Compact RAM/web first installation

Updated 2026-10-15, TY1208Z CA / Hi3798MV100, eMMC 008G30, 1 GiB physical DDR.

The old full-p9 writer was stopped at 5,149,818,880 B, flushed and relocked, before any
p6 write. Automatic continuation stopped. That partial root was not booted.

The compact first installation passes real Chinese LuCI upload/hash confirmation,
official sysupgrade and RAM pivot, 1-GiB p9 writing/full SHA-256 readback, configuration
restoration and p6 kernel writing/readback/relock. The existing CA loader read the
installed kernel from eMMC, verified its CRC and started the real ext4 rw p9 root.
p9 writing took about 29 minutes; full readback about 11 minutes. Single-sector PIO
remains the throughput constraint.

The initial stage2 attempt exposed a missing tr tool; failure returned to upgraded,
which rebooted despite the failure exit. UART intercepted it and recovered the same
accepted RAM system/configuration through CRC-verified TFTP. Both first-install and
daily backends now copy tr and retain a serial RAM recovery shell on failure.
The tmpfs pre-upgrade hook preserves the official configuration backup selection.

First-boot growth exposed two independent integration issues: resize2fs opened
the mounted block device O_RDWR, rejected by the raw-write policy; the MMC queue
advertised erase-based zeroout despite CMD35/36/38 denial. Mounted inspection now
uses O_RDONLY and the mountpoint ioctl, /dev/root resolves to the measured p9, and
persistent candidates no longer advertise discard/WRITE_ZEROES. Cold boot physically
completed growth from 262144 to 1752576 blocks of 4096 B: full 6846-MiB p9, about
6.5 GiB usable filesystem capacity and 6.2 GiB available.

Cold boot also passes configuration hashes, the retained Docker container marker,
automatic Docker 29.6.1 startup and live Chinese Dockerman. The persistent engine
uses the containerd overlayfs snapshotter; the earlier RAM suite's overlay2 label
does not describe this disk-root engine. Slow containerd executable loading exceeded
Docker's 15-second startup deadline. The unchanged native engine APK now preloads
containerd before procd registration and uses bounded respawn.

The first ordinary disk-root reboot exposed del_gendisk waiting on the still mounted
root. One user power cycle restored the installed system. A built repair retains the
persistent MMC host/card, checks idle PIO state and disables interrupts/clock without
card writes. The exact new daily upgrade and one ordinary disk-root reboot now pass
physically; fresh CA/1-GiB/eleven-allocation and shutdown markers are recorded
without UART input. See [native upgrade acceptance](native-web-upgrade-board-20261015.md).

Latest private first-install upload: 132260041 B, SHA-256
9ab558d6ca8a86082efde96154fd867125da02ea9cb1af2f56f892f102d13ad7.
Kernel: 4560012 B, SHA-256
9c1ae8054e2e62251d10ee8cbef79287249bf69be5ab940a80441710408447d5,
ABI 6.12.112~3ff30746f86cc6101046198a6e9bf330-r1.
This rebuilt whole first-install artifact was not flashed again; accepted process
and changed integration evidence are reused. Original RDA firmware, UART, backups
and receipts stay private.

SD, CA fastboot, persistent boot environment, other eMMC partitions and
boot0/boot1/RPMB were not installation targets. No repeated memory/application suite.
