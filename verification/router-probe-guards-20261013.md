# Router board identity and Ethernet probe correction

Date: 2026-10-13. The first integrated application image reached the physical
OpenWrt shell but exposed only loopback. The DT declared
`tianyi,ty1208z-ca-openwrt-router-ram`; the clock, FEMAC resource helper and
FESTAv220 probe accepted only the diagnostic and native Ethernet identities.
Each actual probe therefore rejected this otherwise checked board variant.

All three allowlists now include the router identity. Address, size, extra
resource, PHY address/ID and inherited-control restrictions are unchanged.
The native kernel release is `6.12.112`; variant checks use the rootfs target,
pinned source revision and DT compatible in addition to that release.

`tools/test_ethernet_probe_guards.py` compiles the actual three probe functions
under ASan/UBSan. It accepts all three supported board identities and rejects
a foreign board, changed/missing/extra MMIO resources, forbidden FEMAC reset/
delay properties, another PHY address/ID and MDIO errors. Running this test
against the original compiled router source reproduced the clock-probe
rejection. Both the corrected overlay and the freshly built kernel source
pass `ETHERNET_PROBE_GUARDS_PASS`. The built-source check is required during
RAM packaging, and the overlay check is part of the Ethernet regression.

Core `make lint`, `make build` and `make test` passed. The regenerated kernel
patch, native router build, actual FEMAC sanitizer, two-CRC UART/profile
mutations and both 512/240-MiB application QEMU trials passed locally. The
QEMU trials exercise generic userspace and forwarding; they cannot establish
physical clock, PHY or FEMAC behavior.

The corrected uImage is 3436480 bytes, CRC32 `c018fe3f`, SHA-256
`12b75e8e5e1ceb5e01f13e3c6448704c84b93c574432431becc7709ea4d356ce`.
The separately rebuilt rootfs includes the
[Xray clock correction](xray-browser-clock-20261013.md).
The corrected image subsequently passed physical clock/PHY/eth0, DHCP and
gateway acceptance; see the [board report](openwrt-router-board-20261013.md).

The original TFTP RAM-boot stream has SHA-256
`0955535c707921396ee7ce2736745bc429a2a3f6dfb5eb314a5e29ae0586138c`;
the original shell-inspection stream has SHA-256
`cb25294877e4a444a600e41a2a998baaaadc141a2a78562fb4f8a532553d61c0`.
Raw logs remain in ignored local evidence. No flash or persistent boot change
was performed.

Complete diagnostic CI subsequently passed on `1ac00af`,
[run 38351038836](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38351038836).
The downloaded artifact's eleven manifests and all 109 listed payload files
were verified by size/SHA-256; all ten kernel profiles also pass independent
uImage header/data CRC, load/entry and appended-zImage/DTB checks. The actual
Ethernet log contains `ETHERNET_PROBE_GUARDS_PASS`, `ETHERNET_NET_HELPERS_PASS`
and `FEMAC_DATAPATH_PASS`; its SHA-256 is
`35d329eb518fdc3e30e6381c98db9806aadb58d83f782f2d7683a54bae50456f`.
The eight Wi-Fi sanitizer markers and read-only USB marker were also verified,
and both downloaded RDA patches match that exact Git commit. Native-router
application CI and the later TX-accounting correction are separate; this
diagnostic run does not establish physical traffic or application acceptance.
