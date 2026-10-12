/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef TY1208Z_SAMPLES_H
#define TY1208Z_SAMPLES_H

#include <linux/types.h>

/* Measured Hinas partition starts, expressed as user-area 512-byte sectors. */
#define TY1208Z_SAMPLE_KERNEL 28672U
#define TY1208Z_SAMPLE_EXT4 1249282U /* 610 MiB + 1024-byte superblock offset */

static inline bool ty1208z_sample_sector(u32 sector)
{
	return sector == TY1208Z_SAMPLE_KERNEL ||
	       sector == TY1208Z_SAMPLE_KERNEL + 1 ||
	       sector == TY1208Z_SAMPLE_EXT4 ||
	       sector == TY1208Z_SAMPLE_EXT4 + 1;
}

#endif
