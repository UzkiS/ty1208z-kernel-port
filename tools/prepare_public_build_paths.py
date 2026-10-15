#!/usr/bin/env python3
"""Keep source paths in compiler diagnostics independent of the build account."""
import argparse
import hashlib
from pathlib import Path


def replace_verified(path, expected, before, after):
    data = path.read_bytes()
    original = data.replace(after.encode(), before.encode())
    if hashlib.sha256(original).hexdigest() != expected or original.count(before.encode()) != 1:
        raise ValueError('Pinned build recipe differs: ' + str(path))
    path.write_bytes(original.replace(before.encode(), after.encode()))


def toolchain(source):
    replace_verified(source / 'toolchain/gcc/common.mk',
                     'f5b3b0c1bd86f27a795f37680c729143a993d89773296c1578e01b6f81c828b9',
                     '\tCXXFLAGS_FOR_TARGET="$(TARGET_CFLAGS)" \\\n',
                     '\tCXXFLAGS_FOR_TARGET="$(TARGET_CFLAGS) -ffile-prefix-map=$(TOPDIR)=/build/openwrt" \\\n')


def golang(source):
    replace_verified(source / 'feeds/packages/lang/golang/golang-package.mk',
                     'fafd88dc4d44427169cd097500df8c316cb3515290ffd0206db3fd5667d5bb11',
                     'GO_PKG_BUILD_VARS= \\\n',
                     'GO_PKG_BUILD_VARS= \\\n\tGOFLAGS="-trimpath" \\\n')
    # containerd's legacy per-package flag embeds its absolute GOPATH in Go
    # buildinfo. The global -trimpath above already covers every dependency.
    replace_verified(source / 'feeds/packages/utils/containerd/Makefile',
                     'ef7cf0ba5dcddb87edf09aa617d53f632ec6fc84bda98092d4fbd6264018609a',
                     'MAKE_FLAGS += \\\n\tVERSION=',
                     'MAKE_FLAGS += \\\n\tGO_GCFLAGS= \\\n\tVERSION=')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    golang(args.source)
