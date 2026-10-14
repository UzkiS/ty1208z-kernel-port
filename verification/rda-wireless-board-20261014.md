# RDA5995 wireless integration, 2026-10-14

The integrated single-core native OpenWrt RAM system now supports one RDA5995
USB radio (`1e04:8888`) in WPA2-PSK/CCMP STA or AP mode. Storage remained
request-level read-only throughout. Firmware was extracted from the user's
private backup; firmware, raw logs and network credentials are not public.

| Boundary | Result |
|---|---|
| STA authentication and data | Corrected association IEs include complete RSN information. WPA2 handshake, wireless DHCP and gateway ping pass. |
| AP with a real client | An earlier module completed a phone's WPA2 handshake and DHCP; the user opened the router page. This evidence is reused, not another client trial of the final module. |
| Final module and netifd | STA acquired DHCP and passed 2/2 gateway pings. STA-to-AP loaded AP firmware and reached `AP-ENABLED`. AP teardown stopped its registered foreground wpad process and unloaded the module. Switching back to STA again acquired DHCP and passed gateway ping. |
| Wired management recovery | Handler discovery looped at EOF after wireless scripts were added. UART remained interactive after adapter reconnection. Fixing the loop and restarting netifd restored wired DHCP and SSH. This was not a kernel lockup. |
| Official LuCI RDA form | Checked adaptation offers AP/STA, 2.4 GHz, HT20/legacy, fixed channels, open/WPA2 and auto/CCMP. Running the actual modal builder with form API stubs verifies its options, key dependencies and saved `psk2+ccmp`. The built APK was installed and its minified JS payload matches. A later isolated headless browser verified the Chinese overview/editor and visible WPA2 password input in both modes without saving or applying; see the [UI report](luci-ui-board-20261014.md). |
| Cleanup | Temporary STA/AP networks and private live test settings were removed. The default radio is disabled; wired management remains reachable. |

Final unstripped module SHA-256:
`69a2dd20880ceb2a01f14602d6c990c8e4e93a0fb2de4f5076bda5a378788db1`.
Stripped installed module:
`77c7e37fa8b5834e7407088ab9755c151f6385d48fa961827a263f64c0696634`.
Unchanged native kernel:
`cc89e4a1d64706f2525aeb006a143ac8ca1d22e2c7d9445f7b1180583f17f05d`.

Attach/teardown now owns initialized objects correctly and disables unsupported
P2P. WID decoding accounts for the removed wire length and fixed association
fields. Successful AP GTK installation publishes its index before default-key
selection. USB TX padding extends allocation and zeroes the transfer tail while
retaining logical skb length and error ownership. Role changes use user-space
module/daemon teardown instead of unregistering USB under cfg80211's RTNL lock.

The backend explicitly uses `insmod firmware_path=...` because ubox modprobe
ignores extra parameters. It registers the foreground daemon PID and closes the
serialization lock in its child. It rejects multiple interfaces, mesh, WPA3,
TKIP and bridged STA. Station dump is incomplete and is not accepted evidence.

Changed key/operation/USB-padding functions pass ASan/UBSan; preceding unchanged
association-IE sanitizer evidence is reused. The actual netifd handler completes
a mixed JSON/blank/invalid/EOF fixture (`NETIFD_HANDLER_EOF_PASS`). Module/native
APK compilation, shellcheck, Ruff and repository syntax checks pass. Memory,
Docker and proxy stress suites were not repeated for wireless changes.

| Private receipt | SHA-256 |
|---|---|
| STA association/handshake/data | `8ab435180a6f5c3e7900c211f3907c8ac6c0cf2a83948a542baf3ac5ecbb7b98` |
| Phone AP client/page | `ed24da61e8c3763b44ff362b1c2dd8b1fb9ce297b7804e03f7dc6253f98cbf7c` |
| Earlier netifd STA data | `34cb858851a8e4442ac1570e410389dc5c067b21360ae8f723dd7272ed7312b5` |
| Final netifd AP startup | `9591f31339106aa745ee7e444fdddc9dc866d06d3e05396eb60ca5859d3a95ba` |
| Final AP teardown and STA data | `8bcede39e1ca121631da9aa2c3c33c5be07ae0761c80bbd82064b50d24658cb7` |
| Cleanup and delivered hashes | `7608d2de86316c74114b0e6dff40079825157cf7e7fd6c8ecd4b5777d45d873b` |

The final RAM bootstrap is 22,987,418 bytes, with a 103,696,571-byte supplement.
The offline APK transaction selects 174 packages, including 17 explicit
Docker/UI/wireless requirements; all 107 matching modules have APK owners.
Final backend, netifd EOF and official LuCI changes are in those packages.
Eight declared delivery files, including both kernel check records, were copied
and hash-verified. This is a RAM development delivery with reused component and
measured integration evidence, not an installable or newly whole-image booted firmware.
