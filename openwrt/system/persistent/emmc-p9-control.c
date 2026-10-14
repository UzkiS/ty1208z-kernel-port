/* SPDX-License-Identifier: GPL-2.0-only */
/* RAM-only ioctl helper: fixed measured p6/p9, no sector data writes. */
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
	const char *device = "/dev/mmcblk0p9", *action;
	unsigned int partition = 9;
	unsigned long long expected_size = 7178551296ULL;
	int fd, value, result;

	if (argc == 3 && !strcmp(argv[1], "p6")) {
		device = "/dev/mmcblk0p6";
		partition = 6;
		expected_size = 20971520ULL;
	} else if (argc != 2 && (argc != 3 || strcmp(argv[1], "p9"))) {
		fputs("Usage: emmc-p9-control [p6|p9] unlock|lock|flush\n", stderr);
		return 2;
	}
	action = argv[argc - 1];
	if (strcmp(action, "unlock") && strcmp(action, "lock") && strcmp(action, "flush"))
		return 2;
	fd = open(device, O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		perror("open fixed p6/p9");
		return 1;
	}
	if (fstat(fd, &st) || !S_ISBLK(st.st_mode) || major(st.st_rdev) != 179 ||
	    minor(st.st_rdev) != partition || ioctl(fd, BLKGETSIZE64, &size) ||
	    size != expected_size) {
		fputs("Measured p6/p9 device/size differs\n", stderr);
		close(fd);
		return 1;
	}
	if (!strcmp(action, "flush"))
		result = ioctl(fd, BLKFLSBUF);
	else {
		value = !strcmp(action, "lock");
		result = ioctl(fd, BLKROSET, &value);
	}
	if (result)
		perror("fixed p6/p9 ioctl");
	close(fd);
	return result ? 1 : 0;
}
