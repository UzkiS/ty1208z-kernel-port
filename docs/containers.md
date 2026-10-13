# Docker follow-up

The user requested Docker after board memory, storage and Wi-Fi bring-up.
The board has 1 GiB of physical DDR and a 32-bit Cortex-A7/ARMv7 CPU. The
current RAM experiment intentionally exposes only the low 256 MiB, with the
low 16 MiB reserved. It is not a Docker installation candidate.

Before integration, establish usable higher memory and independently validate
the eMMC driver, block I/O and filesystem/recovery plan. Storage installation
and persistent boot changes retain their separate authorization boundary.

Use pinned OpenWrt container packages and review their real dependencies:
cgroups/resource limits, namespaces, overlayfs, veth/bridge and netfilter.
Keep this optional layer out of the existing diagnostic/router RAM profiles.
First acceptance should run one small `linux/arm/v7` container, exercise DNS
and outbound/forwarded networking with fw4/Passwall, verify memory/CPU limits
and clean shutdown/restart. Confirm image architecture before download;
ARM64-only images cannot run natively on this CPU.

One GiB permits modest workloads; the current single-core experiment, storage
I/O, proxy load and actual free memory must determine the eventual service
budget. Docker and full-memory/storage acceptance remain pending.
