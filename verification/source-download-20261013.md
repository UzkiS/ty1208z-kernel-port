# Pinned source download recovery, 2026-10-13

Diagnostic CI for `57a77c7` failed before compiling the kernel: the BusyBox
HTTPS connection was refused during `urlretrieve`. The Linux archive had
already passed its SHA check. The failure is recorded in
[run 38294845728](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38294845728).
It is a transport failure, not a successful build or an application regression.

The diagnostic build now uses `tools/fetch_pinned_archives.py` for the same
locked Linux/BusyBox URLs and SHA-256 values. It validates existing cache files
and downloads missing archives to unique temporary files. Only a completed
transfer with the exact hash is renamed into the canonical cache path.

Transient connection failures, partial transfers and HTTP 408/429/5xx from
the retry allowlist get at most three attempts with one/two-second delays.
Each attempt has a 20-second socket timeout, a 180-second elapsed deadline
checked between reads and a 512-MiB archive ceiling. A read can take up to the
socket timeout after the elapsed deadline. Wrong hashes, invalid cached files,
certificate-verification failures, HTTPS downgrade redirects and permanent
HTTP errors fail without being accepted or silently replaced. Temporary files
are removed on every exit. No alternate source or TLS bypass was introduced.

Nine file/transport regression tests reproduce connection refusal, partial and
truncated transfers, retry exhaustion/deadlines, bad certificates, HTTP 404/503,
hash failures, invalid metadata, cache checks, redirects/size limits and failed
atomic publication. They run from `make lint` on Windows and Linux without
external network access; transport is mocked, file writes and SHA checks are
real.

A fresh real BusyBox download in a separate local verification directory also
passed: 2565764 bytes, SHA-256
`3311dff32e746499f4df0d5df04d7eb396382d7e108bb9250e7b519b837043a4`.
The actual cached pinned Linux/BusyBox build, core QEMU time64 and guarded boot
regressions pass after the change. Kernel/source versions and generated board
patches are unchanged. Remote CI must still complete to establish the repaired
fresh-run result; local availability does not prove the CI network will work.

The new remote `c25f83d` run [38298432030](https://github.com/UzkiS/ty1208z-kernel-port/actions/runs/38298432030)
has now completed the actual pinned Linux/BusyBox download/build, core time64
and guarded boot steps successfully. Full diagnostic acceptance remains pending;
those completed steps establish recovery of the formerly failing build stage.
