/* SPDX-License-Identifier: ISC */
#ifndef WLAND_PORT_NVRAM_H
#define WLAND_PORT_NVRAM_H

#include <linux/types.h>

int wland_get_mac_address(char *buf);
int wland_set_mac_address(char *buf);
int wland_nvram_read(const char *filename, char *data, int size, int offset);
int wland_file_write(char *filename, char *data, int size, int offset,
		     u32 mode1, u32 mode2);

#endif
