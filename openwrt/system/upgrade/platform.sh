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
		echo 'TY1208Z upgrade stopped; keeping RAM alive for serial recovery.' > /dev/console
		tail -n 30 /tmp/ty1208z-upgrade.log > /dev/console
		# upgraded reboots after any stage2 exit, including an unsuccessful one.
		while :; do
			/bin/ash -i < /dev/console > /dev/console 2>&1
			sleep 1
		done
	}
}
