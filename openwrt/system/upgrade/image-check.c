/* SPDX-License-Identifier: GPL-2.0-only */
/* Bounded, non-extracting parser for the board's deliberately small tar subset. */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <dirent.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

#define LIMIT (1536ULL * 1024 * 1024)
#define MAX_ENTRIES 65536
struct entry { char *name; char *link; unsigned char type; int directory; };
static struct entry entries[MAX_ENTRIES];
static unsigned int count;
static const char *verify_root;
static char linkname[101];
static unsigned int mode;

static void fail(const char *message)
{
	fprintf(stderr, "TY1208Z: %s\n", message);
	exit(1);
}

static void read_exact(FILE *f, void *data, size_t size)
{
	if (fread(data, 1, size, f) != size)
		fail("truncated image");
}

static uint64_t octal(const unsigned char *p, size_t len)
{
	uint64_t n = 0;
	size_t i = 0;
	while (i < len && p[i] == ' ')
		i++;
	for (; i < len && p[i] >= '0' && p[i] <= '7'; i++) {
		if (n > LIMIT)
			fail("tar numeric field exceeds limit");
		n = n * 8 + p[i] - '0';
	}
	for (; i < len; i++)
		if (p[i] && p[i] != ' ')
			fail("unsupported tar number");
	return n;
}

static int zero(const unsigned char *p, size_t n)
{
	while (n--)
		if (*p++)
			return 0;
	return 1;
}

static void skip(FILE *f, uint64_t size, int output)
{
	unsigned char buffer[32768];
	uint64_t remaining = (size + 511) & ~511ULL;
	if (!output && !fseeko(f, (off_t)remaining, SEEK_CUR))
		return;
	clearerr(f); /* A root archive is normally a pipe, not a seekable file. */
	while (remaining) {
		size_t n = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
		read_exact(f, buffer, n);
		if (output && size) {
			size_t payload = size < n ? size : n;
			if (fwrite(buffer, 1, payload, stdout) != payload)
				fail("output failed");
			size -= payload;
		}
		remaining -= n;
	}
}

static uint64_t header(FILE *f, char *name, unsigned char *type)
{
	unsigned char h[512], second[512];
	uint64_t checksum = 0, size;
	read_exact(f, h, sizeof(h));
	if (zero(h, sizeof(h))) {
		read_exact(f, second, sizeof(second));
		if (!zero(second, sizeof(second)))
			fail("bad tar terminator");
		return UINT64_MAX;
	}
	for (unsigned int i = 0; i < sizeof(h); i++)
		checksum += (i >= 148 && i < 156) ? ' ' : h[i];
	if (checksum != octal(h + 148, 8) || memcmp(h + 257, "ustar", 5))
		fail("invalid ustar header/checksum");
	if (h[345])
		snprintf(name, 257, "%.155s/%.100s", h + 345, h);
	else
		snprintf(name, 257, "%.100s", h);
	*type = h[156];
	memcpy(linkname, h + 157, 100);
	linkname[100] = 0;
	mode = octal(h + 100, 8);
	size = octal(h + 124, 12);
	if (size > LIMIT)
		fail("tar member exceeds limit");
	return size;
}

static int find(const char *name)
{
	/* The bounded index is small (the delivery currently has about 5k entries). */
	for (unsigned int i = 0; i < count; i++)
		if (!strcmp(entries[i].name, name))
			return (int)i;
	return -1;
}

static void compare_file(const char *name, unsigned char type, uint64_t size)
{
	char path[1024], target[1024];
	struct stat st;
	unsigned char archive[32768], actual[32768];
	if (snprintf(path, sizeof(path), "%s/%s", verify_root, name) >= (int)sizeof(path) ||
	    lstat(path, &st) || (st.st_mode & 07777) != (mode & 07777))
		fail("staged root file/mode differs");
	if (type == '5') {
		if (!S_ISDIR(st.st_mode))
			fail("staged root directory differs");
		return;
	}
	if (type == '2') {
		ssize_t n = readlink(path, target, sizeof(target));
		if (!S_ISLNK(st.st_mode) || n < 0 || (size_t)n != strlen(linkname) ||
		    memcmp(target, linkname, n))
			fail("staged root symlink differs");
		return;
	}
	if (!S_ISREG(st.st_mode) || (uint64_t)st.st_size != size)
		fail("staged root size/type differs");
	FILE *file = fopen(path, "rb");
	if (!file)
		fail("cannot read staged root file");
	uint64_t padding = ((size + 511) & ~511ULL) - size;
	while (size) {
		size_t n = size < sizeof(archive) ? size : sizeof(archive);
		read_exact(stdin, archive, n);
		read_exact(file, actual, n);
		if (memcmp(archive, actual, n))
			fail("staged root readback differs");
		size -= n;
	}
	fclose(file);
	read_exact(stdin, archive, padding);
}

static void root_check(void)
{
	char name[257], parent[257];
	unsigned char type;
	uint64_t size, total = 0;
	const char *required[] = {"bin/busybox", "sbin/procd", "lib/apk/db/installed",
		"etc/ty1208z-disk-root", "etc/ty1208z-upgrade-abi", "lib/upgrade/platform.sh",
		"sbin/ty1208z-image-check"};
	while ((size = header(stdin, name, &type)) != UINT64_MAX) {
		size_t n = strlen(name);
		if (n && name[n - 1] == '/')
			name[--n] = 0;
		if (!n || name[0] == '/' || strstr(name, "//") || strchr(name, '\\'))
			fail("unsafe root path");
		for (size_t i = 0; i < n; i++)
			if ((unsigned char)name[i] < 32 || (unsigned char)name[i] == 127)
				fail("control character in root path");
		strcpy(parent, name);
		char *part = strtok(parent, "/");
		if (!part || (!strcmp(part, ".") || !strcmp(part, "..")))
			fail("unsafe root component");
		if (strcmp(part, "bin") && strcmp(part, "etc") && strcmp(part, "init") &&
		    strcmp(part, "lib") && strcmp(part, "sbin") && strcmp(part, "usr") &&
		    strcmp(part, "var") && strcmp(part, "www"))
			fail("image attempts to replace a preserved data directory");
		while ((part = strtok(NULL, "/")))
			if (!strcmp(part, ".") || !strcmp(part, ".."))
				fail("unsafe root component");
		if (find(name) >= 0 || count == MAX_ENTRIES)
			fail("duplicate root path or too many entries");
		strcpy(parent, name);
		for (char *p = strchr(parent, '/'); p; p = strchr(p + 1, '/')) {
			*p = 0;
			int index = find(parent);
			if (index < 0 || !entries[index].directory)
				fail("root entry has a missing or non-directory parent");
			*p = '/';
		}
		if (type != '0' && type != 0 && type != '2' && type != '5')
			fail("unsupported root tar type (links/devices/PAX)");
		if ((type == '2' || type == '5') && size)
			fail("unexpected directory/link payload");
		total += ((size + 4095) & ~4095ULL) + 8192;
		if (total > LIMIT)
			fail("expanded root exceeds limit");
		entries[count].name = strdup(name);
		if (!entries[count].name)
			fail("out of memory");
		entries[count].link = strdup(linkname);
		if (!entries[count].link)
			fail("out of memory");
		entries[count].type = type;
		entries[count++].directory = type == '5';
		if (verify_root)
			compare_file(name, type, size);
		else
			skip(stdin, size, 0);
	}
	/* Only zero tar padding may follow the root stream. */
	int ch;
	unsigned int padding = 0;
	while ((ch = getchar()) != EOF)
		if (ch || ++padding > 10240)
			fail("unexpected data after root archive");
	if (ferror(stdin))
		fail("root archive read failed");
	for (unsigned int i = 0; i < sizeof(required) / sizeof(required[0]); i++)
		if (find(required[i]) < 0)
			fail("essential root file absent");
	const char *top[] = {"bin", "etc", "lib", "sbin", "usr", "var", "www"};
	for (unsigned int i = 0; i < sizeof(top) / sizeof(top[0]); i++)
		if (find(top[i]) < 0 || (!entries[find(top[i])].directory &&
			!(strcmp(top[i], "var") == 0 && entries[find(top[i])].type == '2' &&
			  !strcmp(entries[find(top[i])].link, "tmp"))))
			fail("managed root entry must be a directory");
	if (find("init") < 0 || entries[find("init")].directory || entries[find("init")].type == '2')
		fail("managed init entry must be a regular file");
	printf("%llu\n", (unsigned long long)total);
	for (unsigned int i = 0; i < count; i++)
		free(entries[i].link);
	for (unsigned int i = 0; i < count; i++)
		free(entries[i].name);
}

static void outer(const char *path, const char *member)
{
	const char *names[] = {"manifest", "kernel", "rootfs.tar.gz"};
	uint64_t limits[] = {4096, 20 * 1024 * 1024, 256 * 1024 * 1024};
	char name[257];
	unsigned char type;
	uint64_t size;
	struct stat st;
	FILE *f = fopen(path, "rb");
	if (!f || fstat(fileno(f), &st) || !S_ISREG(st.st_mode) ||
	    st.st_size > 280 * 1024 * 1024)
		fail("not a bounded regular firmware file");
	for (unsigned int i = 0; i < 3; i++) {
		size = header(f, name, &type);
		if (size == UINT64_MAX || strcmp(name, names[i]) || type != '0' || !size || size > limits[i])
			fail("unexpected outer member, type or length");
		skip(f, size, member && !strcmp(name, member));
	}
	if (header(f, name, &type) != UINT64_MAX)
		fail("extra outer member");
	/* fwtool metadata follows tar padding; it is independently checked upstream. */
	if ((uint64_t)st.st_size - (uint64_t)ftello(f) > 65536)
		fail("excessive outer trailer");
	fclose(f);
}

static uint32_t be32(const unsigned char *p)
{
	return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}

static uint32_t crc32(const unsigned char *p, size_t n)
{
	uint32_t crc = ~0U;
	while (n--) {
		crc ^= *p++;
		for (int i = 0; i < 8; i++)
			crc = (crc >> 1) ^ (0xedb88320U & -(crc & 1));
	}
	return ~crc;
}

static void kernel_check(const char *path)
{
	struct stat st;
	FILE *f = fopen(path, "rb");
	if (!f || fstat(fileno(f), &st) || st.st_size < 64 || st.st_size > 20 * 1024 * 1024)
		fail("bad kernel size");
	unsigned char *p = malloc(st.st_size);
	if (!p)
		fail("out of memory");
	read_exact(f, p, st.st_size);
	uint32_t hcrc = be32(p + 4);
	memset(p + 4, 0, 4);
	if (be32(p) != 0x27051956 || be32(p + 12) != (uint64_t)st.st_size - 64 ||
	    be32(p + 16) != 0x02000000 || be32(p + 20) != 0x02000000 ||
	    p[28] != 5 || p[29] != 2 || p[30] != 2 || p[31] != 0 ||
	    crc32(p, 64) != hcrc || crc32(p + 64, st.st_size - 64) != be32(p + 24))
		fail("kernel uImage identity/CRC mismatch");
	free(p);
	fclose(f);
}

static int p9_path(const char *path)
{
	struct stat st;
	return !stat(path, &st) && (st.st_dev == makedev(179, 9) || st.st_dev == makedev(179, 6) ||
		(S_ISBLK(st.st_mode) && (st.st_rdev == makedev(179, 9) ||
		 st.st_rdev == makedev(179, 6) || st.st_rdev == makedev(179, 0))));
}

static void released(void)
{
	DIR *proc = opendir("/proc");
	struct dirent *de;
	char path[512], line[4096];
	if (!proc)
		fail("cannot inspect process references");
	while ((de = readdir(proc))) {
		if (strspn(de->d_name, "0123456789") != strlen(de->d_name))
			continue;
		snprintf(path, sizeof(path), "/proc/%s/mountinfo", de->d_name);
		FILE *f = fopen(path, "r");
		if (!f)
			continue; /* A process may have exited. */
		while (fgets(line, sizeof(line), f)) {
			unsigned int major_id, minor_id;
			if (sscanf(line, "%*u %*u %u:%u", &major_id, &minor_id) == 2 &&
			    major_id == 179 && (minor_id == 9 || minor_id == 6 || minor_id == 0))
				fail("p9 is still mounted in a process namespace");
		}
		fclose(f);
		snprintf(path, sizeof(path), "/proc/%s/maps", de->d_name);
		f = fopen(path, "r");
		if (f) {
			while (fgets(line, sizeof(line), f)) {
				unsigned int major_id, minor_id;
				if (sscanf(line, "%*s %*s %*s %x:%x", &major_id, &minor_id) == 2 &&
				    major_id == 179 && (minor_id == 9 || minor_id == 6 || minor_id == 0))
					fail("process mapping still references old root");
			}
			fclose(f);
		}
		const char *refs[] = {"root", "cwd", "exe"};
		for (unsigned int i = 0; i < 3; i++) {
			snprintf(path, sizeof(path), "/proc/%s/%s", de->d_name, refs[i]);
			if (p9_path(path))
				fail("process still references old root");
		}
		snprintf(path, sizeof(path), "/proc/%s/fd", de->d_name);
		DIR *fds = opendir(path);
		struct dirent *fd;
		if (!fds)
			continue;
		while ((fd = readdir(fds))) {
			char target[1024];
			snprintf(target, sizeof(target), "%s/%s", path, fd->d_name);
			if (p9_path(target))
				fail("open file still references old root");
		}
		closedir(fds);
	}
	closedir(proc);
	FILE *swaps = fopen("/proc/swaps", "r");
	if (!swaps)
		fail("cannot inspect swap");
	while (fgets(line, sizeof(line), swaps))
		if (sscanf(line, "%511s", path) == 1 && p9_path(path))
			fail("p9 swap is active");
	fclose(swaps);
}

int main(int argc, char **argv)
{
	if (argc == 2 && !strcmp(argv[1], "root"))
		root_check();
	else if (argc == 3 && !strcmp(argv[1], "verify-root")) {
		verify_root = argv[2];
		root_check();
	}
	else if (argc == 2 && !strcmp(argv[1], "released"))
		released();
	else if (argc == 3 && !strcmp(argv[1], "outer"))
		outer(argv[2], NULL);
	else if (argc == 4 && !strcmp(argv[1], "member") &&
		 (!strcmp(argv[3], "manifest") || !strcmp(argv[3], "kernel") || !strcmp(argv[3], "rootfs.tar.gz")))
		outer(argv[2], argv[3]);
	else if (argc == 3 && !strcmp(argv[1], "kernel"))
		kernel_check(argv[2]);
	else
		fail("invalid image-check command");
	return 0;
}
