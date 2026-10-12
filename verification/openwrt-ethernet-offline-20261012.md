# Native OpenWrt Ethernet RAM candidate: offline acceptance

Date: 2026-10-12. This is native build/emulation acceptance. The physical
Ethernet report covers the separate diagnostic image, not this OpenWrt
image. No flashing or persistent boot changes were performed.

## Actual image identity

| Item | Observed build result |
|---|---|
| Kernel | `6.12.112-ty1208z-openwrt-net` |
| Native source | OpenWrt `58efa9917d4cc53fceed173529a286187649e827` |
| Compiler / libc | Native GCC 14.3.0 / musl 1.2.5; completed fixed toolchain reused |
| uImage bytes | 4689784 |
| uImage SHA-256 | `b2182d940f546032686077278baab6114ddaf6b17a43e39f728afc8bc29e23ee` |
| zImage SHA-256 | `ec7bec961bc623233ce6c6b9e49affa04f33ce135a97c6729e371ba525cfb21d` |
| Expanded Image SHA-256 | `d0fe3e4c3f200fa030f97049e6af028d4a32ffde9aa4dfec4df191e45495dd95` |
| Physical decompression footprint | `0x00008000..0x009bbcc0`, below 16 MiB |
| Appended DTB SHA-256 | `8eb36890678a829cdf37de760c6d659f05aa03fb46d256bc06dd520326f87b46` |
| Actual BusyBox SHA-256 | `265c11cf740a23af8c0e0f38e62821475003728c9264262bf9157d01dc16c24e` |
| Actual ARM iperf3 SHA-256 | `6950a4e6e56e7ddd4a9208683eee286493441ba44f7f2a700476e87adfb5bd8b` |

The distinct `net` subtarget includes native netifd/DHCP, ethtool and iperf3
3.20. It inherits measured UART/timer/memory and Ethernet resources through
the authoritative board patch/DTS, with exact FESTAv220 PHY and clock guards.
Storage, USB, modules, SMP, netfilter and Wi-Fi remain disabled. The network
configuration is one DHCP client plus loopback; DHCP serving and SSH are
disabled. No install/sysupgrade image is defined.

## Checks and discovered integration issues

- The standalone base build and generic ARM/RAM time64/boot-protocol tests
  passed after extending the driver guards to the distinct native profile.
- The actual native target compiled its kernel and userspace. Resolved target,
  overlay/recipe identities, compiled DT, kernel configuration, uImage CRC,
  appended DT and actual kernel decompression footprint passed.
- OpenWrt's hidden `IPV6` default and enabled kernel debugfs initially violated
  the narrow experiment checks. The isolated tree now overrides the hidden
  IPv6 default and explicitly disables kernel debugfs; validation remains
  strict. Its kernel recipe omits the unsupported `modules` make goal while
  keeping `CONFIG_MODULES=n`. The plain RAM/apps trees are unchanged.
- Native BusyBox disables installer/list output and lacks base64. Checks
  execute the actual ARM traffic applets instead of assuming `--list` exists.
  UART/QEMU script transfer uses bounded printf octal chunks, needing no
  extra applet and avoiding the 512-byte serial editing limit.
- Actual native-patched RX/NAPI/ISR/TX-monitor functions passed ASan/UBSan
  datapath regression. Native serial PTY integration rejects foreign kernel/
  rootfs identities, echoed completion markers and incomplete binding/results;
  all transmitted script lines remain below 256 bytes.
- The actual native kernel/embedded rootfs passed QEMU virt with no guest NIC:
  musl time64, procd/ubus, UCI, logging and RAM-file timestamps at 2040. The
  actual iperf3 client/server completed a loopback exchange at that future
  clock and produced `OPENWRT_ETHERNET_TOOLS_PASS`. This is tool emulation,
  not hardware Ethernet performance. The plain RAM target also passed after
  the shared serial-script transport change.
- Moving compiler reuse into the native-source layer preserved application
  configuration resolution; pinned Passwall/Xray selections passed again.

## Still required on the board

Fresh remote CI also completed both plain native RAM and isolated Ethernet
builds/emulation on `62db42b`: [run 38287462054](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38287462054).
Both artifact uploads succeeded, explicitly labeled HARDWARE-UNTESTED. This
reproduces the offline checks; it does not establish a board boot or the later
application/UDP/NTP integration.

The guarded RAM plan must pass against the recorded bootloader inspection,
and a fresh live loader identity/DDR/bootcmd and device CRC must pass before
boot. Then verify actual OpenWrt startup, PHY binding, netifd lease, gateway
replies, bidirectional TCP transfers, errors/interrupts and cable reconnect.
Complete PHY initialization, Passwall routing and Wi-Fi are separate unfinished
milestones. This candidate remains hardware untested and is not flashable.
