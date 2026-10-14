# Project instructions

Scope: this repository only. The unrelated drive-root `AGENTS.md` is excluded.
Session instructions take precedence.

## Objective and current state

Maintain TY1208Z CA / Hi3798MV100 board support and pinned official OpenWrt.
The physical system now has eMMC ext4 rw installation, full p9 growth, native
Chinese LuCI upgrades, persistent Docker data/autostart and ordinary command
reboot. RDA STA/AP and USB VFAT/NTFS read-only access have measured evidence.
Read `STATUS.md`, `docs/architecture.md` and `docs/hardware.md` before board changes.
Older profile reports describe their dated scope, not current missing features.

## User defaults

- Use pinned official OpenWrt sources. Required features are Simplified Chinese,
  Docker/Dockerman, Passwall with both Xray and sing-box, and unzip.
- Default root password is empty. Preserve explicitly configured passwords on
  configuration restoration; never create a random management password.
- Use accepted graceful command reboot paths when their exact prerequisites
  hold. Avoid repeated manual power cycles.
- Prefer a practical single-device workflow and lower token use. Keep backup,
  boot and recovery checks; reuse passing unchanged memory/application evidence
  and test only changed integration boundaries. Do not repeat full suites,
  add variants, or download/reverify CI without a concrete need. Inferred
  coverage must not be reported as new measured acceptance.
- Current limits are single-core, low768 memory (about744 MiB usable), slow
  single-sector PIO, request-level read-only SD and no measured Wi-Fi-uplink
  bypass-routing composition. Do not expand these requirements on your own.
- Every enlarged RAM-profile boot requires fresh attached loader inspection and
  the immediately preceding guarded reboot's complete hash-verified eleven
  allocations. Preserve low16 MiB and exclude upper256 MiB. Keep the dedicated
  low init pages reserved. DDR capacity or ddrfree alone does not permit growth.
- Public usage documentation is Chinese and written for repository readers.
  Separate current guides from dated evidence. Preserve historical measurements
  and identify reused component evidence. Do not narrate conversation history.
- Public content must omit credentials, actual network identities, unique device
  identifiers and personal local paths. Do not mention this cleanup in Git
  commit titles or bodies.

## Authorization and device boundaries

- Offline analysis, edits, builds, tests, local commits and pushing to the
  configured repository were authorized. Routine work does not need approval.
- The prior session explicitly authorized measured p6/p9 installation and
  necessary recovery; those installation/upgrade milestones have passed.
  This does not authorize unrelated device writes or expanded partition targets.
- Preserve the known-successful CA fastboot, persistent boot environment,
  p1-p5/p7-p8, SD, boot0/boot1/RPMB and security state.
- Never generate or execute OTP/eFuse, key, lock-bit or security-state writes.
- No guessed load/boot commands. Verify exact bootloader commands, allocation
  evidence, resource ranges and both device CRCs for RAM loading.
- Keep original RDA firmware, full firmware packages, backups, credentials,
  raw UART and private receipts outside public Git.
- Do not spawn agents unless the user explicitly requests delegation.

## Architecture and source ownership

- New Linux files are authoritative in `overlay/`; regenerate
  `patches/0001-hi3798mv100-diagnostic.patch`. Never edit generated patches alone.
- Existing upstream changes use explicit checked generators that fail on
  changed anchors, archive hashes or patch context.
- Pin source versions, URLs and SHA-256 identities. Do not download and execute
  upstream scripts. Preserve licenses; fetch SDK reference files with
  `tools/fetch_references.py` rather than vendoring complete trees or firmware.
- Wi-Fi sources remain in `wifi/`, native integration in `openwrt/`.
  Modules must match the exact target build; never copy Hinas4.4 or another
  OpenWrt target's modules into Linux6.12.

## Validation and Git

- UTF-8/LF; Python four spaces; kernel C uses upstream tabs/style.
- Build outputs stay under ignored `.work/` and `artifacts/`.
- Runtime changes normally require `make lint`, `make build`, `make test`,
  selected according to the explicit changed-boundary preference above.
  Documentation changes need accuracy, links and source hygiene checks, not
  another kernel build. Run meaningful integration checks, not mirror tests.
- QEMU virt validates generic boot/userspace, not MV100 controllers, Wi-Fi,
  physical memory or CA loading. Future wall-clock tests run only in isolated
  QEMU. Normal board diagnostics do not change wall time.
- Never label a new offline artifact hardware-accepted merely because unchanged
  components passed earlier. Record build, emulation, hardware and application
  status separately, with exact identities and remaining limits.
- Commit coherent changes. No force-push/history rewriting, credentials,
  firmware, raw DTBs, upstream tarballs or large binaries.
- Actions uses pinned revisions, read-only permissions and fresh Linux builds.
  Check actual outcomes after authorized pushes or targeted dispatches;
  skipped, configured or queued checks are not passing evidence.
