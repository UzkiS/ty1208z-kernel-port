/* SPDX-License-Identifier: GPL-2.0-only */
/* Reuse the accepted bounded tar, uImage and released-device checks. */
#define main native_upgrade_main
#include "../upgrade/image-check.c"
#undef main

static void first_outer(const char *path, const char *member)
{
	const char *names[] = {"manifest", "kernel", "rootfs.ext4.gz"};
	uint64_t limits[] = {4096, 20 * 1024 * 1024, 256 * 1024 * 1024};
	char name[257];
	unsigned char type;
	struct stat st;
	FILE *f = fopen(path, "rb");
	if (!f || fstat(fileno(f), &st) || !S_ISREG(st.st_mode) ||
	    st.st_size > 280 * 1024 * 1024)
		fail("not a bounded first-install file");
	for (unsigned int i = 0; i < 3; i++) {
		uint64_t size = header(f, name, &type);
		if (size == UINT64_MAX || strcmp(name, names[i]) || type != '0' || !size || size > limits[i])
			fail("unexpected first-install member/type/length");
		skip(f, size, member && !strcmp(name, member));
	}
	if (header(f, name, &type) != UINT64_MAX ||
	    (uint64_t)st.st_size - (uint64_t)ftello(f) > 65536)
		fail("extra first-install member/trailer");
	fclose(f);
}

static uint32_t le32(const unsigned char *p)
{
	return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void ext4_check(void)
{
	unsigned char buffer[32768];
	uint64_t bytes = 4096;
	read_exact(stdin, buffer, 4096);
	const unsigned char *sb = buffer + 1024;
	/* Exact 1-GiB/4-KiB clean ext4 with the project filesystem UUID. */
	const unsigned char uuid[] = {0xaf,0x36,0xaa,0x90,0x9d,0x68,0x42,0x6c,
		0xa0,0x70,0x37,0xf3,0x98,0xd7,0x12,0x08};
	if (sb[56] != 0x53 || sb[57] != 0xef || le32(sb + 4) != 262144 ||
	    le32(sb + 24) != 2 || sb[58] != 1 || sb[59] || le32(sb + 336) ||
	    memcmp(sb + 104, uuid, sizeof(uuid)))
		fail("compact ext4 identity/geometry/state differs");
	size_t n;
	while ((n = fread(buffer, 1, sizeof(buffer), stdin))) {
		bytes += n;
		if (bytes > 1073741824ULL)
			fail("expanded first-install root too large");
	}
	if (ferror(stdin) || bytes != 1073741824ULL)
		fail("truncated first-install ext4");
}

int main(int argc, char **argv)
{
	if (argc == 3 && !strcmp(argv[1], "outer"))
		first_outer(argv[2], NULL);
	else if (argc == 4 && !strcmp(argv[1], "member") &&
		 (!strcmp(argv[3], "manifest") || !strcmp(argv[3], "kernel") || !strcmp(argv[3], "rootfs.ext4.gz")))
		first_outer(argv[2], argv[3]);
	else if (argc == 2 && !strcmp(argv[1], "ext4"))
		ext4_check();
	else if (argc == 3 && !strcmp(argv[1], "kernel"))
		kernel_check(argv[2]);
	else if (argc == 2 && !strcmp(argv[1], "released"))
		released();
	else
		fail("invalid first-install check command");
	return 0;
}
