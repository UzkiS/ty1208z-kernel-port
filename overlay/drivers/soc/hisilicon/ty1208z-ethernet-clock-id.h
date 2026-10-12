/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _TY1208Z_ETHERNET_CLOCK_ID_H
#define _TY1208Z_ETHERNET_CLOCK_ID_H

#include <linux/delay.h>
#include "ty1208z-ethernet-audit.h"

struct ty1208z_eth_clock_result {
	u32 before;
	u32 enabled;
	u32 restored;
	u32 phy_id;
	bool changed;
	bool restore_verified;
};

/* Only the exact cold-boot state measured in ethernet-audit1 is accepted. */
static inline bool ty1208z_eth_clock_state(u32 phy_crg, u32 select,
					 u32 phy_addr, u32 ldo)
{
	return phy_crg == 0x101 && select == 0x0e000004 &&
	       phy_addr == 0x03000001 && ldo == 0x8;
}

/* Volatile bit-3 experiment, NOT a clock provider or cold-start sequence. */
static inline int ty1208z_eth_clock_id(void __iomem *crg, void __iomem *mdio,
				     u32 phy_crg, u32 select, u32 phy_addr,
				     u32 ldo, struct ty1208z_eth_clock_result *result)
{
	int ret;

	*result = (struct ty1208z_eth_clock_result) { 0 };
	result->before = readl(crg);
	if (result->before != 3 ||
	    !ty1208z_eth_clock_state(phy_crg, select, phy_addr, ldo))
		return -ENODEV;
	writel(result->before | BIT(3), crg);
	result->changed = true;
	result->enabled = readl(crg);
	/* Never access MDIO or overwrite unexpected control state. */
	if (result->enabled != 0xb)
		return -EIO;
	/* SDK hieth waits 5 ms after supplying MDCK, before any MDIO access. */
	mdelay(5);
	ret = ty1208z_eth_read_phy_id(mdio, &result->phy_id);
	result->restored = readl(crg);
	if (result->restored != 0xb)
		return -EBUSY;
	writel(result->before, crg);
	result->restored = readl(crg);
	result->restore_verified = result->restored == result->before;
	return result->restore_verified ? ret : -EIO;
}

#endif
