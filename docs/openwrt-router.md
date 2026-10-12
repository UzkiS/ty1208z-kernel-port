# Native OpenWrt applications and Ethernet RAM integration

`make openwrt-router TASKBASE=/absolute/linux/build-root` builds a separate
`TASKBASE/router/` source/output tree using the same pinned compiler, feeds,
Passwall patches and kernel patch as the application target. It reuses the
`apps` package subtarget with an explicit variant marker and merges the measured
FEMAC/MDIO/FESTAv220 configuration. The standalone diagnostic, native Ethernet
and plain application trees retain their own configurations and outputs.

The candidate includes Passwall/Xray/LuCI, fw4, dnsmasq-full, ip-full, ethtool
and iperf3. Its modules match its exact native kernel. The rootfs uses the
reviewed DHCP-client-only `probe` interface on eth0 and no DHCP-server interface.
Kernel storage, USB, Wi-Fi, SMP, debugfs and restart experiments are excluded.
Physical services, credentials, clock synchronization and routing policy still
need hardware acceptance before normal use. There is no flash/install recipe.

## Application and forwarding acceptance

The actual matched kernel/initrd first passes the existing isolated 2040
DNS/TLS/LuCI/rpcd/Passwall SOCKS and VLESS TLS fixture. Network namespaces then
create a client and origin through veth pairs; netifd configures router-side
links/routes and fw4 generates forwarding rules. Actual HTTPS traffic and
forward counters must pass.

The fixture also verifies bounded UDP delivery through a real namespace-origin
iperf3 server. It removes forwarding and requires direct HTTPS and the UDP
test's TCP control connection to fail. It starts the installed Passwall service
with its real VLESS TLS node, TCP/UDP
TPROXY mode and generated nft/policy-routing/Xray setup. Client HTTPS must
succeed without a SOCKS option. Forward and reverse UDP transfers must each
report more than 4096 received bytes and ten packets. Actual UDP TPROXY counters
and routing table 999 must be populated. After stopping Passwall, HTTPS and the
UDP test's control connection must fail again.
No host networking or disks are exposed to QEMU.

Both 512-MiB and `mem=240M` trials pass the same fixture. Provenance binds exact
kernel/config/rootfs/packages/console hashes and variant. These are emulated
forwarding/TCP/UDP TPROXY checks; they do not measure physical Ethernet,
routing speed, cable recovery, NTP, Wi-Fi or whole-system Y2038 behavior.

## Checked RAM output

`artifacts/openwrt-router1/` contains an ordinary uImage with appended DTB and
separate bounded gzip/newc initrd at `0x04000000`. It uses the same measured
Ethernet nodes as the native Ethernet experiment. The wrapper checks complete
application provenance, exact board/clock/PHY/helper sources, actual built
FEMAC datapath sanitizer and low-16-MiB decompression footprint. Both device
CRCs gate the measured boot command through the common external-initrd tooling.

Only the distinct application Ethernet identity permits network, modules,
netfilter and IPv6 together. Existing diagnostic/Ethernet restrictions remain
unchanged. Per-resource/config/provenance mutations and either CRC failure
stop the flow. The UART network/iperf collector supports `--profile router`,
requiring the exact router kernel and apps rootfs identity before experiments;
default `--profile net` retains the independent Ethernet workflow.

Application CI has separate matrix jobs for plain and integrated RAM builds.
Each uses a fresh native compiler/build, locked serial dependency, both memory
trials, packaging and PTY checks. Artifacts are HARDWARE-UNTESTED. See the
[local result](../verification/openwrt-router-offline-20261013.md) for exact
identity and limits; a queued CI job is not acceptance.
