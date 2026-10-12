/* SPDX-License-Identifier: GPL-2.0-only */
/* Optional RAM diagnostic: expose decoded fields, without new card commands. */
#ifdef CONFIG_MMC_DW_HI3798MV100_IDENT
MMC_DEV_ATTR(ty1208z_ident,
	"EMMC_IDENT_COMPLETE sectors=%u bytes=%llu ext_rev=%u clock=%u bus_width=%u timing=%u\n",
	card->ext_csd.sectors, (unsigned long long)card->ext_csd.sectors * 512,
	card->ext_csd.rev, card->host->ios.clock, card->host->ios.bus_width,
	card->host->ios.timing);
#endif
