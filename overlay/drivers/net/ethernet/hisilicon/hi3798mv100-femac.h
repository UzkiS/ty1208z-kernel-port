/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_FEMAC_H
#define HI3798MV100_FEMAC_H

/* SDK hieth.c port setup; global base is physical MAC + 0x1300. */
static inline void hi3798mv100_femac_setup(void __iomem *port, void __iomem *global)
{
	u32 value;

	value = readl(global + 0x18);
	writel(value | BIT(0) | BIT(1), global + 0x18);
	value = readl(port + 0x218);
	writel(value & ~GENMASK(25, 23), port + 0x218);
	value = readl(port + 0x210);
	writel(value & ~BIT(18), port + 0x210); /* No negotiated pause offload. */
	value = readl(port + 0x380);
	writel(value & ~BIT(14), port + 0x380); /* Software checks packet checksums. */
}

static inline void hi3798mv100_femac_reset(void __iomem *global)
{
	u32 value = readl(global + 0x8) & ~BIT(0);

	/* Single wired port; vendor sequence pulses the global MAC reset twice. */
	writel(value | BIT(0), global + 0x8);
	usleep_range(1000, 10000);
	writel(value, global + 0x8);
	usleep_range(1000, 10000);
	writel(value | BIT(0), global + 0x8);
	usleep_range(1000, 10000);
	writel(value, global + 0x8);
	usleep_range(1000, 10000);
}

static inline bool hi3798mv100_femac_valid_length(u32 frame)
{
	/* Length includes the FCS. Check BEFORE subtraction and skb_put. */
	return frame >= ETH_HLEN + ETH_FCS_LEN && frame <= MAX_FRAME_SIZE;
}

#endif
