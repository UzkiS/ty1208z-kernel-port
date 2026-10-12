/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _TY1208Z_ETHERNET_AUDIT_H
#define _TY1208Z_ETHERNET_AUDIT_H

#include <linux/bitops.h>
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/iopoll.h>

/* SDK clock/reset fields, not a clock provider or an initialization sequence. */
static inline bool ty1208z_eth_inherited_ready(u32 mac_crg, u32 phy_crg,
					      u32 select, u32 phy_addr)
{
	return (mac_crg & 0x1b) == 0x0b && (phy_crg & 0x11) == 1 &&
	       !(select & BIT(8)) && (phy_addr & 0x1f) == 1;
}

/* Exactly PHY 1, Clause 22 ID registers 2 and 3. No PHY register writes. */
static inline int ty1208z_eth_read_phy_id(void __iomem *mdio, u32 *phy_id)
{
	u32 status, id = 0;
	unsigned int reg;
	int ret;

	for (reg = 2; reg <= 3; reg++) {
		ret = readl_poll_timeout(mdio, status, status & BIT(15), 1, 1000);
		if (ret)
			return ret;
		/* Ready bit 15 is set by hardware; bit 13 would request a write. */
		writel(BIT(8) | reg, mdio);
		ret = readl_poll_timeout(mdio, status, status & BIT(15), 1, 1000);
		if (ret)
			return ret;
		id = (id << 16) | (readl(mdio + 4) & 0xffff);
	}
	if (!id || id == 0xffffffff)
		return -ENODEV;
	*phy_id = id;
	return 0;
}

#endif
