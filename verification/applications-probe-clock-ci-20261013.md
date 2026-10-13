# Fresh Xray/probe application CI

Application CI [38351038848](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38351038848)
completed successfully on `1ac00af24f1c01f89634547b8a4a203ef013f6f1`.
This revision includes the router probe guards, Xray startup-before-NTP fix
and delivered peer-DNS default; it predates the later TX counter correction
and Chinese default.

All four downloaded artifacts were inspected independently. Each RAM variant
contains six files whose actual lengths/SHA-256 match its manifest. uImage
header/payload CRCs, exact raw-kernel-plus-DTB, fixed load/entry, initrd gzip
length and bounded external range passed. Four actual QEMU consoles and their
provenance match the packages/kernel/rootfs/config identities. Every recorded
marker occurs in the real console; all guest fixture-source hashes match this
exact Git revision, and NTP fixture binaries match their recorded hashes.

| Variant / usable MiB | Actual console bytes | SHA-256 |
|---|---:|---|
| Plain / 512 | 110906 | `e3411bdfe181c79fdf8adb75764675a374cbe8af02c92aa171e71d3d740480d5` |
| Plain / 240 | 110891 | `abaaccd0ce126c54eda989fab2ecd9b21b50ede9132ab903eb6e3acb2d4faf7e` |
| Router / 512 | 126657 | `5e4cce6bc44798371a0ad2d64d5381a1ad4596431aa3b7801c57cdc233fcbeda` |
| Router / 240 | 126699 | `3c52d88c9ee7ad524ac4cca6ee82ea928e4c187f952662b8e9f9cc72ee05b37d` |

All trials contain `XRAY_UNSYNCHRONIZED_CLOCK_PASS`, NTP era/time64,
DNS/TLS/HTTPS, authenticated LuCI/rpcd and Passwall SOCKS/TLS markers. Router
trials additionally contain actual netifd/fw4 forwarding and TCP/UDP TPROXY
markers. This is fresh software acceptance, not physical USB/radio, routing
throughput, whole-system Y2038 or a persistent installation result.
