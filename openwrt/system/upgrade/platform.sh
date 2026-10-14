#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# shellcheck disable=SC2034
REQUIRE_IMAGE_METADATA=1
RAMFS_COPY_BIN="$RAMFS_COPY_BIN /sbin/ty1208z-upgrade /sbin/ty1208z-image-check /sbin/emmc-p9-control sha256sum readlink df stat tr head mktemp jshn"

platform_check_image() {
	/sbin/ty1208z-upgrade validate "$1" || return 74
}

platform_do_upgrade() {
	/sbin/ty1208z-upgrade apply "$1" "${UPGRADE_BACKUP:-}" || {
		echo 'TY1208Z upgrade stopped; inspect /tmp/ty1208z-upgrade.log before recovery.' >&2
		exit 1
	}
}
