// SPDX-License-Identifier: GPL-2.0-only
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

/* Both directories stay on p9. A crash exposes either complete /etc tree. */
int main(void)
{
	struct stat live, staged;
	if (lstat("/etc", &live) || lstat("/.ty1208z-reset/etc", &staged) ||
	    !S_ISDIR(live.st_mode) || !S_ISDIR(staged.st_mode) ||
	    live.st_dev != staged.st_dev || geteuid() != 0) {
		fputs("Invalid reset directories\n", stderr);
		return 1;
	}
	if (renameat2(AT_FDCWD, "/etc", AT_FDCWD,
		      "/.ty1208z-reset/etc", RENAME_EXCHANGE)) {
		perror("Atomic configuration exchange");
		return 1;
	}
	sync();
	return 0;
}
