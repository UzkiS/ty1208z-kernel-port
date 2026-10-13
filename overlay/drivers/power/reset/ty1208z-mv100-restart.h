/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef TY1208Z_MV100_RESTART_H
#define TY1208Z_MV100_RESTART_H

#include "ty1208z-sp805-restart.h"

/* MV100's original FDT supplies an AMBA ID override. On this physical board
 * the ID cells are absent (zero); the actual inactive watchdog registers and
 * independently measured SYSID0 provide the narrow RAM-experiment guard.
 */
static inline bool ty1208z_mv100_restart_ready(void __iomem *base,
					     void __iomem *sysid)
{
	struct ty1208z_sp805_state state;

	if (readl(sysid) != 0x37980100)
		return false;
	ty1208z_sp805_observe(base, &state);
	return state.peripheral_id == 0 && state.cell_id == 0 &&
		state.control == 0 && readl(base) == 0xffffffff &&
		readl(base + 0x004) == 0xffffffff &&
		readl(base + 0x010) == 0 && readl(base + 0x014) == 0 &&
		readl(base + 0xc00) == 0;
}

static inline bool ty1208z_mv100_restart(void __iomem *base,
				       void __iomem *sysid)
{
	if (!ty1208z_mv100_restart_ready(base, sysid))
		return false;
	/* Same source-backed WDG0 protocol; no clock/security/storage writes. */
	writel(0x1acce551, base + 0xc00);
	writel(0, base + 0x008);
	writel(0x100, base);
	writel(3, base + 0x008);
	readl(base + 0xc00);
	return true;
}

#endif
