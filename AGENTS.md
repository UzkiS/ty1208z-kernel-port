# Project instructions

Scope: this repository only. The user excluded the unrelated drive-root
`AGENTS.md` from this task. Session instructions take precedence.

## Objective and current boundary

Port TY1208Z CA / Hi3798MV100 to a modern Linux kernel, then integrate official
OpenWrt, Passwall and the board's Wi-Fi, with real time64 validation.
The first deliverable is a single-core, RAM-only diagnostic candidate.
Read `STATUS.md`, `docs/architecture.md` and `docs/hardware.md` before changing
board support. Keep assumptions separate from measured facts.

## User defaults

- The user dropped Kwrt customization on 2026-10-13. Use official OpenWrt
  sources and pin the latest selected branch commit for reproducible builds.
- Required user features: board support, Simplified Chinese, Docker,
  Passwall with both Xray and sing-box, and unzip. Docker runtime acceptance
  depends on measured higher-memory, storage and container-kernel support;
  compiling packages alone does not satisfy that requirement.
- New OpenWrt images use Simplified Chinese and an empty root password
  by default, as requested on 2026-10-13. Do not generate or install a random
  management password during RAM setup. Preserve a password explicitly set by
  the user only when restoring that user's configuration.
- The user requested autonomous command reboots on 2026-10-13 to avoid repeated
  manual power cycles. The native router RAM module and guarded UART reboot are
  physically accepted; use that measured path when its exact prerequisites hold.
  The separate `sd-ident1` and `sd-ro1` profiles also pass physical command
  restart, verified DW shutdown and automatic return to the exact router.
  `sd-ro1` physically accepts block reads and a VFAT file read with enforced
  request-level write denial; native-router integration and hotplug are pending.
  Other RAM profiles still
  need separate restart/shutdown support and acceptance.

## Authorization

- Offline source analysis, editing, building, testing, local Git commits and
  pushing to the user-provided repository are authorized by the session.
- Do not repeatedly ask approval for routine work in that scope.
- No hardware flashing or persistent boot changes are authorized by that scope.
  Before a later installation, establish the actual partition layout, backups,
  recovery method and exact proposed image, and obtain session authorization.
- Preserve the known-successful CA fastboot. Do not substitute the generic one.
- Never generate or execute OTP/eFuse, key, lock-bit or security-state writes.
- Do not assume RAM boot bypasses authentication. No guessed load/boot commands:
  first establish current bootloader commands and actual usable RAM/reservations.
- Do not spawn agents unless the user explicitly requests delegation.

## Architecture and source ownership

- Kernel board support in `overlay/` and `config/` builds independently of Wi-Fi
  and OpenWrt. `docs/architecture.md` describes optional integration layers.
- `overlay/` is authoritative for new Linux files. Modify it, then regenerate
  `patches/0001-hi3798mv100-diagnostic.patch`; do not edit generated patches alone.
- Changes to existing upstream files belong in explicit, checked generators.
  Fail on changed anchors, archive hashes or patch context.
- Pin upstream versions, download URLs and hashes in `config/sources.lock.json`.
  Never download and execute upstream scripts. Preserve applicable licenses.
- Fetch SDK reference files using `tools/fetch_references.py`; do not vendor a
  complete SDK/kernel tree or republish the user's firmware.
- Modules must match the exact kernel build. Do not carry Hinas 4.4 modules into
  a Linux 6.12 build or copy modules from another OpenWrt target.

## Engineering and validation

- UTF-8, LF, four spaces for Python; upstream kernel C uses tabs/kernel style.
- Keep build output in `.work/` and `artifacts/`, outside tracked sources.
- Run `make lint`, `make build` and `make test` for build/runtime changes.
  A lint-only or documentation change need not trigger another kernel build.
- Use meaningful integration checks: required Kconfig options, absence of disk
  drivers, image CRC/structure, static ARM ELF, ARM shell and time64 round trips.
- QEMU virt validates generic kernel/initramfs/userspace only. It does not test
  MV100 UART/interrupt/timer drivers, Wi-Fi, RAM placement or CA authentication.
- Future wall-clock tests run only inside an isolated QEMU guest. Normal board
  diagnostics do not change wall time and write test files only under RAM `/tmp`.
- Never label an offline candidate boot-verified, flashable or a working router.
  Record build, emulation, hardware and application status separately.
- Hardware reports must include observed chip/USB IDs and anonymized logs.
  Remove credentials, MAC addresses and local personal paths before publishing.

## Git and CI

- Work on `main` initially; use focused branches as parallel features grow.
- Commit coherent milestones with concise problem/behavior-focused messages.
- Never force-push, rewrite user history, commit credentials or add firmware,
  build directories, raw DTBs, upstream tarballs or large binary artifacts.
- GitHub Actions uses read-only permissions, pinned action revisions and a
  fresh Linux build. Upload diagnostics as explicitly UNTESTED artifacts.
- After an authorized push, check the actual Actions result. CI configuration
  existing in Git is not evidence that it ran successfully.
