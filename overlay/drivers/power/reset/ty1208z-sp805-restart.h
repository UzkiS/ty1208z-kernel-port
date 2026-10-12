/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef TY1208Z_SP805_RESTART_H
#define TY1208Z_SP805_RESTART_H

#include <linux/io.h>
#include <linux/types.h>

struct ty1208z_sp805_state {
	u32 peripheral_id;
	u32 cell_id;
	u32 control;
};

static inline void ty1208z_sp805_observe(void __iomem *base,
				       struct ty1208z_sp805_state *state)
{
	unsigned int i;

	state->peripheral_id = 0;
	state->cell_id = 0;
	for (i = 0; i < 4; i++)
		state->peripheral_id |= (readl(base + 0xfe0 + i * 4) & 0xff) << (i * 8);
	for (i = 0; i < 4; i++)
		state->cell_id |= (readl(base + 0xff0 + i * 4) & 0xff) << (i * 8);
	state->control = readl(base + 0x008);
}

static inline bool ty1208z_sp805_restart_ready(const struct ty1208z_sp805_state *state)
{
	/* Real AMBA identity, never a DT ID override. Require the inherited
	 * watchdog to be disabled; this driver never takes over a running one.
	 */
	return (state->peripheral_id & 0x00ffffff) == 0x00141805 &&
		state->cell_id == 0xb105f00d && state->control == 0;
}

static inline bool ty1208z_sp805_restart(void __iomem *base)
{
	struct ty1208z_sp805_state state;

	ty1208z_sp805_observe(base, &state);
	if (!ty1208z_sp805_restart_ready(&state))
		return false;
	/* SP805 unlock/load/control, as used by the upstream SP805 restart
	 * handler. The pinned MV100 restart recipe uses a short 0x100 load.
	 * Only an explicit kernel restart reaches these writes.
	 */
	writel(0x1acce551, base + 0xc00);
	writel(0, base + 0x008);
	writel(0x100, base + 0x000);
	writel(3, base + 0x008);
	readl(base + 0xc00); /* Flush posted writes before waiting for reset. */
	return true;
}

#endif
