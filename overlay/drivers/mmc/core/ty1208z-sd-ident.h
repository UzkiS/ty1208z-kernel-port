/* SPDX-License-Identifier: GPL-2.0-only */
/* Decoded non-unique metadata only; reading this attribute sends no commands. */
#ifdef CONFIG_MMC_DW_HI3798MV100_SD_IDENT
MMC_DEV_ATTR(ty1208z_sd_ident,
	"SD_IDENT_COMPLETE bytes=%llu clock=%u bus_width=%u timing=%u\n",
	(unsigned long long)card->csd.capacity << card->csd.read_blkbits,
	card->host->ios.clock, card->host->ios.bus_width, card->host->ios.timing);
#endif
