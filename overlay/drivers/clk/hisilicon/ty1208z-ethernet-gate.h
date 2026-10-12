/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef TY1208Z_ETHERNET_GATE_H
#define TY1208Z_ETHERNET_GATE_H

#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/io.h>

static inline int ty1208z_ethernet_gate_disable(void __iomem *crg)
{
	/* Never overwrite a control value changed by another owner. */
	if (readl(crg) != 0xb)
		return -EBUSY;
	writel(3, crg);
	return readl(crg) == 3 ? 0 : -EIO;
}

static inline int ty1208z_ethernet_gate_enable(void __iomem **control)
{
	static const u32 expected[] = { 3, 0x101, 0x0e000004, 0x03000001, 8 };
	unsigned int i;

	for (i = 0; i < 5; i++)
		if (readl(control[i]) != expected[i])
			return -ENODEV;
	if (readl(control[0]) != 3)
		return -EBUSY;
	writel(0xb, control[0]);
	if (readl(control[0]) != 0xb)
		return -EIO;
	/* MDCK settling delay from the pinned vendor clock path. */
	mdelay(5);
	return 0;
}

#endif
