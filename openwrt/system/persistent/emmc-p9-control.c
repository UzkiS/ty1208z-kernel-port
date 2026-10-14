/* SPDX-License-Identifier: GPL-2.0-only */
/* RAM-only diagnostic helper: fixed measured p9, no sector data writes. */
#include <errno.h>
#include <fcntl.h>
#include <linux/fs.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	unsigned long long size;
	struct stat st;
	int fd, value, result;

	if (argc != 2 || (strcmp(argv[1], "unlock") &&
			  strcmp(argv[1], "lock") && strcmp(argv[1], "flush"))) {
		fputs("Usage: emmc-p9-control unlock|lock|flush (fixed mmcblk0p9)\n", stderr);
		return 2;
	}
	fd = open("/dev/mmcblk0p9", O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		perror("open fixed p9");
		return 1;
	}
	if (fstat(fd, &st) || !S_ISBLK(st.st_mode) || major(st.st_rdev) != 179 ||
	    minor(st.st_rdev) != 9 || ioctl(fd, BLKGETSIZE64, &size) ||
	    size != 7178551296ULL) {
		fputs("Measured p9 device/size differs\n", stderr);
		close(fd);
		return 1;
	}
	if (!strcmp(argv[1], "flush"))
		result = ioctl(fd, BLKFLSBUF);
	else {
		value = !strcmp(argv[1], "lock");
		result = ioctl(fd, BLKROSET, &value);
	}
	if (result)
		perror("fixed p9 ioctl");
	close(fd);
	return result ? 1 : 0;
}
