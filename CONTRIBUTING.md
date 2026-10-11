# Contributing

Read `AGENTS.md` and `STATUS.md` first. Keep patches focused on an independently
testable change. Record the upstream version, why the change is needed, and the
validation that actually ran.

For kernel or diagnostic userspace changes:

1. Edit authoritative source/config/generators, not just the generated patches.
2. Run `make lint`, `make build`, then `make test` in Linux.
3. Review generated patch and config differences. Check the output manifest.
4. Update the relevant status/assumptions. Attach logs for failures or hardware
   observations; remove credentials, MAC addresses and personal paths.
5. Commit source, patches and concise results. Keep firmware and binary output
   outside Git. Confirm the corresponding GitHub Actions run after pushing.

Documentation-only changes require lint and a review for accuracy. Do not repeat
a full build for unchanged kernel/userspace sources after tests passed.

Do not infer physical-board validation from QEMU virt results. Storage, wired
network, Wi-Fi station/AP, Hinas compatibility and Passwall need their own tests.
No persistent installation work belongs in an offline diagnostic milestone.
