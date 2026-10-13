# Isolated application DNS handover, 2026-10-13

Application CI [run 38318338793](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38318338793)
on `5aa1af4` built the native application image, then failed during QEMU
runtime acceptance. The downloaded console records the installed dnsmasq
receiving SIGTERM followed by the fixture instance failing to bind
`127.0.0.1` with `Address in use`. NTP and certificate checks had passed;
the DNS/TLS/application acceptance did not complete in that run.

The QEMU-only guest fixture now waits, with a ten-second bound, for installed
dnsmasq processes to exit after the init-script stop. It also verifies that
its own replacement DNS process remains alive during and after resolver
acceptance. It does not retry a failed service indefinitely or accept
another resolver's answer after its own process exits. All fixture clock,
process and file operations occur inside the isolated RAM guest.

The existing plain-application and Ethernet/router ARM images were retested
with this exact guest script, each with 512-MiB and 240-MiB usable budgets.
All four tests passed the installed NTP 2036/2038/2040 cases, DNS, certificate
expiry and HTTPS validation, authenticated LuCI/Passwall, actual SOCKS/TLS
data flow and nftables checks. Both router budgets additionally passed
netifd/fw4 forwarding and actual TCP/UDP TPROXY. Console files were hashed
against each generated provenance report; the report's guest-script hash
matches the changed source.

| Variant | Usable MiB | Console SHA-256 |
|---|---:|---|
| Applications | 512 | `0eb17dcfa2c3c917a21f36fbc14f7e85470dd1ac7dc32a46a9f362c7813ce269` |
| Applications | 240 | `488eb07cd0af582ff546128462aeb593d941d81e75c19a1285cb96e7b5acc804` |
| Router | 512 | `85c8b993adf887cb3b80409e435c66b182f22a245b2c00ea4b8cfc0e8dbf267b` |
| Router | 240 | `054936417bd1bf70971a8bedee31bf1176fc0244edf19d841e60d3322f2d162e` |

Guest-script SHA-256:
`88553a54ed7c7ef61d7f224b96745820b963c3a64102af3561666439532f4b18`.
These are local runtime reruns using existing native images, not fresh
application rebuilds or physical-board acceptance. Fresh CI is pending.
