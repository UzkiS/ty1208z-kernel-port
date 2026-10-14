# USB mass storage and NTFS physical acceptance

2026-10-15, TY1208Z CA / Hi3798MV100. Official OpenWrt 25.12 commit
58efa9917d4cc53fceed173529a286187649e827, Linux 6.12.112.

## Device and measured access

The inserted USB2 high-speed (480 Mbit/s enumeration, not a throughput claim)
storage device identifies as 320a:827b, SORAYA Portable storage. It exposes
122142464 x 512 B = 62536941568 B (about 58.2 GiB), removable /dev/sda.
The existing large /dev/sda1 is NTFS; /dev/sda2 is a 32-MiB VFAT boot partition.
Serial, UUIDs, personal filenames and raw logs remain private.

The preceding storage kernel passed exact USB/block identity checks, a VFAT
ro,nosuid,nodev,noexec mount, a 4-KiB file read/hash and unmount. The main NTFS
partition exposed a missing filesystem driver. The persistent kernel fragment
now enables built-in NTFS3 and LZX/XPRESS support; its exact kernel, modules,
RDA module and APK database were rebuilt together, without a foreign module.

The new kernel passes a real NTFS3 ro,nosuid,nodev,noexec mount, a nonempty file's
first 64-KiB sample/hash and unmount. The whole USB disk's write-I/O and written
sector counters are identical before/after this operation. No formatting,
partition changes, filesystem repair, force mount or USB writes occurred.
Both partitions are left unmounted. USB write support/performance, exFAT and
external ext4 were not newly measured; SD remains driver-enforced read-only.

## Exact delivered upgrade

Native daily image: 131399882 B, SHA-256
38d42824f3189e24f079ec8693e334076736dce07fb8854c38e38079937544a2.
p6 kernel: 4677436 B, SHA-256
3f16be94a64beb6ad8860bf84760ddb381fb7bfedaccefa13bfbae16ba2d621d.
Kernel ABI: 6.12.112~120d00c44db5befcdb6ed8d1f6825a56-r1.

Official Chinese LuCI uploaded and validated the exact SHA-256, kept configuration
and dispatched normal sysupgrade/stage2. Default eMMC boot returned without UART
input or a manual power cycle. Receive-only UART records the accepted shutdown
markers, CA loader, 1-GiB DDR and all eleven allocations. Root is ext4 rw p9;
p6/other partitions and SD remain read-only. Configuration/account/key bytes
match the private backup after removing only native Docker's duplicate network
list entries. Docker 29.6.1 autostarts with /opt/docker and overlayfs.

Ordinary reboot, container content persistence, Chinese mount UI, memory,
Ethernet, proxy, Wi-Fi STA/AP and time64 evidence are reused from the accepted
unchanged components. They were not repeated as a new full function matrix.
The official block-mount source tries ntfs3 for a detected ntfs filesystem.
No persistent USB mount setting was saved.

Latest first-install package: 132372681 B, SHA-256
895305f7d0bf2200dbb3bb6b7641e5ae50136d770f3fd861add18e65ac2d4e76.
This whole first-install package was not reflashed; the prior measured first
installation process and the changed kernel/upgrade boundary are reused.
Original RDA firmware and all firmware packages are private local delivery.

Private upgrade UART SHA-256: db83a8a3beb986202a21faaebac99c50e08a8aaa455d7a9849dc7c3a2d368553.
