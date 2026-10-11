#!/usr/bin/env python3
"""Generate the diagnostic patch from a verified, pristine Linux archive."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import tarfile

project = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--archive", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
lock = json.loads((project / "config/sources.lock.json").read_text())
with args.archive.open("rb") as source:
    assert hashlib.file_digest(source, "sha256").hexdigest() == lock["linux"]["sha256"]

changes = {
    "arch/arm/mach-hisi/Kconfig": (
        'config ARCH_HI3xxx\n',
        'config ARCH_HI3798MV100\n'
        '\tbool "Hi3798MV100 single-core diagnostic support"\n'
        '\tdepends on ARCH_MULTI_V7 && !SMP\n'
        '\tselect HI3798MV100_TIMER\n'
        '\thelp\n'
        '\t  Experimental RAM-only diagnostic candidate for TY1208Z CA.\n'
        '\t  Hardware boot and secure-boot acceptance remain unverified.\n\n'
        'config ARCH_HI3xxx\n'),
    "arch/arm/mach-hisi/Makefile": (
        'obj-y\t+= hisilicon.o\n',
        'obj-y\t+= hisilicon.o\nobj-$(CONFIG_ARCH_HI3798MV100) += hi3798mv100.o\n'),
    "arch/arm/boot/dts/hisilicon/Makefile": (
        '# SPDX-License-Identifier: GPL-2.0\n',
        '# SPDX-License-Identifier: GPL-2.0\n'
        'dtb-$(CONFIG_ARCH_HI3798MV100) += hi3798mv100-ty1208z-diagnostic.dtb\n'),
    "drivers/clocksource/Kconfig": (
        'config ARM_TIMER_SP804\n',
        'config HI3798MV100_TIMER\n'
        '\tbool\n\tdepends on ARM && OF\n'
        '\tselect CLKSRC_MMIO\n\tselect TIMER_OF\n\n'
        'config ARM_TIMER_SP804\n'),
    "drivers/clocksource/Makefile": (
        'obj-$(CONFIG_ARM_TIMER_SP804)',
        'obj-$(CONFIG_HI3798MV100_TIMER) += timer-hi3798mv100.o\n'
        'obj-$(CONFIG_ARM_TIMER_SP804)'),
}
diffs = []
with tarfile.open(args.archive) as archive:
    for path, (old, new) in changes.items():
        before = archive.extractfile(f'linux-{lock["linux"]["version"]}/{path}').read().decode()
        assert before.count(old) == 1, f"Patch anchor not unique: {path}"
        after = before.replace(old, new)
        diffs.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{path}", f"b/{path}"))
for source in sorted((project / "overlay").rglob("*")):
    if source.is_file():
        path = source.relative_to(project / "overlay").as_posix()
        diffs.extend(difflib.unified_diff([], source.read_text().splitlines(True), "/dev/null", f"b/{path}"))
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("".join(diffs), encoding="utf-8", newline="\n")
print(f"Generated {args.output} from verified Linux {lock['linux']['version']}")
