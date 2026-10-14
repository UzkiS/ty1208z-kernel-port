# Native Docker, fw4 and Passwall combined QEMU acceptance

2026-10-14: one independent native OpenWrt source/kernel/rootfs now passes real
Docker, procd, firewall4 and both installed Passwall cores together in isolated
Cortex-A7 QEMU. Chinese LuCI, empty default root password, unzip and the existing
time64/application suite pass in the same guest. This is ARMv7 userspace/kernel
composition evidence. Physical Docker/storage, MV100 peripheral integration,
restart, RDA Wi-Fi/STA/AP and installation remain unverified.

## Source and reusable entry

Run `make build` and `make openwrt-toolchain`, then:

```text
make openwrt-container-applications TASKBASE=/absolute/linux/build-root
```

The entry independently prepares `TASKBASE/container-applications/`, builds the
actual Chinese/application/Docker rootfs, verifies selected configuration and
real ARM APK versions, runs the 768-MiB suite and exports its coherent evidence.
`make openwrt-container-app-config` stops after selection checks.
Docker/dockerd 29.6.1, containerd 2.2.5, runc 1.3.6 and tini 0.19.0 use the same
locked official packages feed and native GCC/musl as the application rootfs.
firewall4 supplies the firewall provider; its official `fw3 -> fw4` compatibility
alias is accepted, while an independent legacy fw3 binary is rejected.

Official OpenWrt commit is `58efa9917d4cc53fceed173529a286187649e827`; a live
GitHub branch query on 2026-10-14 still returned that `openwrt-25.12` head.
The freshly prepared native source uses board patch
`e8487bf7ba471700e0604d790454c22912e37445b12e625800118b99844638f7`, not the older
cached patch used by the separate standalone Docker report. The source overlay
and actual kernel/config/package identities are recorded. That patch identity
does not establish physical acceptance of this independent QEMU-only kernel.

The profile selects containers as installed packages and `kmod-nft-nat` alongside
Chinese LuCI, Passwall/Xray/sing-box, unzip and firewall4. MMC, MTD, USB, board
Ethernet and SMP are excluded; block support satisfies the declared container
Btrfs dependency. The physical RAM packager rejects both the marker and this
variant. No uImage, physical board DTB or persistent installation is produced.

## Actual guest and composition

QEMU virt/cortex-a7 runs one CPU with 768 MiB, `-nic none`, no disks or host
mounts. Its additional entry requires dummy-virt and the explicit command-line
gate before executing the unmodified native OpenWrt `/init`. That actual init
switches to tmpfs. Native BusyBox/procd stay intact; normal Docker/runc pivot_root
works without DOCKER_RAMDISK or disabling pivot_root. The suite checks the
actual tmpfs mount. All topology/configuration/data writes stay in guest RAM.

The fixture is made from the delivered native initrd, leaving the original
native archive/staging tree unchanged. It adds a separately named static BusyBox
helper, resource probe, local deterministic `linux/arm/v7` container and guest
script. Native automatic dockerd boot is suppressed only in this fixture; the
test explicitly configures and starts its real `/etc/init.d/dockerd` procd service.
The container includes exact musl/libgcc payloads from the same native archive
so Docker's real native tini can run inside it. No registry is contacted.

- Actual procd service state, overlay2, cgroup v2 and ARMv7 Docker info pass.
  The 64-MiB/0.5-CPU/32-PID container reads exact limits and seccomp mode 2;
  the bounded CPU workload produces nonzero throttling. PID limits are read
  back, without a fork-limit stress or cpuset/swap-limit claim.
- A separate 32-MiB container performs bounded page touching. Its own cgroup
  reaches the limit, the kernel reports CONSTRAINT_MEMCG, and Docker reports
  exit 137/OOMKilled. This is intentional container OOM, not guest-wide OOM.
  `docker run --init` independently checks real docker-init as container PID 1.
- A real user bridge resolves `service` through 127.0.0.11 and serves the exact
  HTTP payload. Real UCI/netifd/firewall4 configure an external guest namespace.
  Default and user bridge requests reach its CGI with the masqueraded peer
  address. That namespace reaches Docker's published port with the userland
  proxy disabled, establishing DNAT/forwarding.
- Existing netifd/fw4 forwarding and bidirectional UDP fixtures pass. Direct
  TLS requests from the persistent container's actual network namespace fail
  before proxy startup. The installed Passwall service with Xray succeeds,
  stopping it denies requests, and the real sing-box redirection succeeds with
  a nonzero nft TPROXY counter. Stopping sing-box denies requests again.
  The requesting curl binary is native OpenWrt curl entered into that container
  network namespace; this is not an in-container curl filesystem test.
- Docker embedded DNS/HTTP, masquerade and published DNAT remain functional
  after the actual fw4 and Passwall reloads/start/stop sequence. Service containers
  stop with exit 0, are removed, their bridge and external veth/namespace disappear,
  and the actual procd Docker/containerd processes stop normally. Saved guest UCI
  configurations are restored and checked with fw4.
- The same guest passes Chinese/empty-password LuCI and rpcd authentication,
  both Passwall SOCKS/TLS cores, certificate expiry, native DNS/HTTPS, ZIP/ZIP64
  extraction and installed NTP across the 2036 era and 2038 time32 boundaries
  to 2040. Future clocks occur only in QEMU. The physical board clock is unchanged.

All 26 required markers appear exactly once and the final console has no panic
or application failure marker. Sources, original/native outputs and generated
fixtures are hashed before preparation/runtime and checked again before success.
Failed reruns invalidate previous successful provenance before preparation.

## Delivery and validation boundaries

`artifacts/openwrt-container-applications-qemu/manifest.json` inventories the
exact kernel, native and fixture initrds, compiled configurations, package list,
native overlay/locks, core-package report, helper/probe, ZIP/NTP fixtures and
QEMU console/provenance. The exporter checks the complete required marker list,
current runtime/source hashes, core-package checks and their equality with the
native application kernel/config/locks before copying and rehashing each file.
It also requires the currently reviewed board patch. A failed build/export
removes the prior delivery success manifest. The large QEMU-only initrds are
outside the measured physical RAM transfer budget and are not board candidates.

The canonical local build/test/export completed successfully. All 17 combined
delivery and 13 native core files were independently checked against their
manifests, copied to the Windows workspace and hashed again. Required markers
and the actual console identity were independently verified.

| Canonical output | Bytes | SHA-256 |
|---|---:|---|
| zImage.QEMU-ONLY | 3625488 | `d61361e6b0f13270b784bf2e51349d808a69977815b901da41c2b1c4023ef5ed` |
| rootfs.native.QEMU-ONLY.cpio.gz | 108719102 | `f0015940414130cb089b2c8de3a0b289716b9f359af22164b747e54bdb60295c` |
| rootfs.fixture.QEMU-ONLY.cpio.gz | 115651066 | `b63d1e7150aa304f0757618a2f342607685ebc74a1aec3d036edb8d1ab41b0ac` |
| qemu.log | 152861 | `d28a5abeac8235fad419c2635def603045e31a75512439ba93296a8adf9125b0` |
| delivery manifest.json | 8054 | `7adc8cb64422f1be58f13cc762dc17b8ece2f2bb4de3f973e8f163e7a8907925` |

Native and fixture cpio expand to 319754752 and 323301376 bytes respectively.

The separate standalone Docker default fixture remains a regression target
after adding optional native libraries for tini; that canonical runtime rerun
also passed all eleven markers. Required `make lint`,
`make build` and `make test`, plus the existing 240-MiB native router application
suite, pass locally and cover shared tooling and the non-container conditional
guest path.
The dedicated pinned, read-only CI workflow builds a fresh toolchain/source and
executes this same build/test/export command. Fresh combined remote CI is pending
until its actual result and downloaded evidence are verified.

The separate corrected eMMC RAM candidate subsequently passed physical
read-only blocks/ext4/shutdown/restart and exact router/configuration return;
see its [board report](emmc-ro-board-20261014.md). It uses a newer 9DE8 board
patch; the combined QEMU evidence above remains tied to its recorded E848
patch and is not rehashed. Backups, native storage integration, a verified
storage-backed Docker board candidate, RDA firmware/STA/AP and final routing
remain required. After the user reconnected TTL, actual COM9 reception and
interactive input recovered. The second native SD trial returned to the exact
original Chinese router through one guarded command restart, measured SD
shutdown, fresh CA-loader inspection and both device CRCs. An immediate backup
preserved current configuration; Chinese authenticated UI, empty root login,
restart binding and IRQ Err0 pass after return. The full goal remains
active/incomplete.
