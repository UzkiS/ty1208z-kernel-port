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
application rebuilds or physical-board acceptance.

Fresh native application CI subsequently passed on `6b53448`,
[run 38342674311](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38342674311).
Both plain and router jobs rebuilt their native images and completed both
memory budgets. All four downloaded artifacts were independently inspected:
each RAM manifest's six payload files match their sizes/hashes, uImage header
and data CRCs pass, initrd size/address match, and all four actual console
files match their provenance hashes and required acceptance markers. The
fixture-source hashes were compared with that exact Git commit, including the
same bounded DNS-handover script above; downloaded NTP binaries also match.

| CI variant | Usable MiB | Console SHA-256 |
|---|---:|---|
| Applications | 512 | `e7eeb8bd0bd246824f59579f23a408700da0d5167231f565819abdc04543324c` |
| Applications | 240 | `e287cb1f6853982899d4ab5b5dfefe09b2bf17c4fa4d409c9e3938385a000e20` |
| Router | 512 | `241f884bf9a82f654ff0a1dd4d4d6ba1904eb250bf46cf019ed7e845e547253e` |
| Router | 240 | `8331f11c146c4faf8edff8b3100700010c56a90fca2921425b38793e31879f2e` |

This establishes fresh CI acceptance of the fixture correction. That commit
predates the later physical-router probe, pre-NTP Xray and DHCP-DNS-default
corrections; this run does not validate those newer changes or physical
Ethernet routing.
