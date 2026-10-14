#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# shellcheck disable=SC2034
REQUIRE_IMAGE_METADATA=1
RAMFS_COPY_BIN="$RAMFS_COPY_BIN /sbin/ty1208z-first-install /sbin/ty1208z-first-check /sbin/emmc-p9-control sha256sum readlink head mktemp jshn tr"
RAMFS_COPY_DATA="$RAMFS_COPY_DATA /etc/ty1208z-first-installer"

first_install_stop() {
	echo 'TY1208Z installation stopped; keeping RAM alive for serial recovery.' > /dev/console
	[ ! -f /tmp/ty1208z-first-install.log ] || tail -n 30 /tmp/ty1208z-first-install.log > /dev/console
	# upgraded reboots even when stage2 exits unsuccessfully. Stay here so a
	# failed installation can never automatically boot the partial eMMC root.
	while :; do
		/bin/ash -i < /dev/console > /dev/console 2>&1
		sleep 1
	done
}

platform_check_image() {
	/sbin/ty1208z-first-install validate "$1" || return 74
}

platform_pre_upgrade() {
	# Official sysupgrade skips archive creation on tmpfs. This RAM-only
	# installer still retains the official selected configuration file list.
	if [ -n "${UPGRADE_BACKUP:-}" ]; then
		/sbin/sysupgrade --list-backup > /tmp/ty1208z-first-conffiles || first_install_stop
		sed -i 's,^/,,' /tmp/ty1208z-first-conffiles || first_install_stop
		tar -C / -czf "$UPGRADE_BACKUP" -T /tmp/ty1208z-first-conffiles || first_install_stop
	fi
}

platform_do_upgrade() {
	/sbin/ty1208z-first-install apply "$1" "${UPGRADE_BACKUP:-}" || first_install_stop
}
