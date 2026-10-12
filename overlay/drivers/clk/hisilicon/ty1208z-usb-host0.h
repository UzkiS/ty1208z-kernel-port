/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Independent implementation of the host0 register protocol documented by
 * Hisilicon's 2014/2015 clk-hiusb2.c (Apache-2.0, Liu Hui).
 * Register values/order are hardware protocol facts. No SDK C implementation
 * is included here; the offline test executes the pinned original as oracle.
 */
#ifndef TY1208Z_USB_HOST0_H
#define TY1208Z_USB_HOST0_H

#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/types.h>

/* Five separately bounded mappings: CRG46, CRG47, USB0, USB1, SYSID0. */
#define TY_USB_CONTROLLER_RESETS 0x00037000U
#define TY_USB_CONTROLLER_CLOCKS 0x0000007fU
#define TY_USB_PHY_RESETS 0x00000f00U
#define TY_USB_PHY_POWER_RESETS 0x00000500U
#define TY_USB_PHY_PORT_RESETS 0x00000a00U

struct ty1208z_usb_phy_command {
	u32 value;
	unsigned int delay_us;
};

static inline void ty1208z_usb_phy_commands(void __iomem *port,
			const struct ty1208z_usb_phy_command *commands,
			unsigned int count)
{
	unsigned int i;

	for (i = 0; i < count; i++) {
		writel(commands[i].value, port);
		if (commands[i].delay_us)
			udelay(commands[i].delay_us);
	}
}

/* The original SYSID0 low-byte revision decision does not require an OTP read. */
static inline bool ty1208z_usb_revision_valid(u32 sysid0)
{
	return sysid0 != 0 && sysid0 != ~0U;
}

static inline int ty1208z_usb_host0_stop(void __iomem * const *controls)
{
	u32 value = readl(controls[1]);

	writel(value | TY_USB_PHY_RESETS, controls[1]);
	udelay(100);
	/* Match host0 last-user shutdown; preserve all other clock/control bits. */
	value = readl(controls[0]);
	writel(value & ~0x71U, controls[0]);
	udelay(200);
	return (readl(controls[1]) & TY_USB_PHY_RESETS) == TY_USB_PHY_RESETS &&
	       !(readl(controls[0]) & 0x71U) ? 0 : -EIO;
}

static inline int ty1208z_usb_host0_start(void __iomem * const *controls)
{
	static const struct ty1208z_usb_phy_command pll240[] = {
		{ 0xa809, 0 }, { 0xe809, 0 }, { 0xa809, 300 },
	};
	static const struct ty1208z_usb_phy_command revision10[] = {
		{ 0xa801, 0 }, { 0xe801, 0 }, { 0xa801, 300 },
		{ 0xa604, 0 }, { 0xe604, 0 }, { 0xa604, 1000 },
		{ 0xa01c, 0 }, { 0xe01c, 0 }, { 0xa01c, 0 },
		{ 0xb01c, 0 }, { 0xf01c, 0 }, { 0xb01c, 100 },
	};
	static const struct ty1208z_usb_phy_command other_revision[] = {
		{ 0xa73b, 0 }, { 0xe73b, 0 }, { 0xa73b, 500 },
		{ 0xabc0, 0 }, { 0xebc0, 0 }, { 0xabc0, 500 },
		{ 0xa73f, 0 }, { 0xe73f, 0 }, { 0xa73f, 1000 },
		{ 0xabe0, 0 }, { 0xebe0, 0 }, { 0xabe0, 1000 },
		{ 0xaa02, 0 }, { 0xea02, 0 }, { 0xaa02, 0 },
		{ 0xba1e, 0 }, { 0xfa1e, 0 }, { 0xba1e, 500 },
		{ 0xa801, 0 }, { 0xe801, 0 }, { 0xa801, 300 },
	};
	u32 revision = readl(controls[4]);
	u32 value;

	if (!ty1208z_usb_revision_valid(revision))
		return -ENODEV;

	value = readl(controls[0]);
	writel(value | TY_USB_CONTROLLER_RESETS, controls[0]);
	udelay(200);
	value = readl(controls[1]);
	writel(value | TY_USB_PHY_RESETS, controls[1]);
	udelay(200);
	value = readl(controls[2]);
	writel((value | 8U) & ~0x201U, controls[2]);
	udelay(100);
	value = readl(controls[1]);
	writel(value | 3U, controls[1]);
	udelay(300);
	ty1208z_usb_phy_commands(controls[3], pll240, ARRAY_SIZE(pll240));
	value = readl(controls[1]);
	writel(value & ~TY_USB_PHY_POWER_RESETS, controls[1]);
	udelay(300);
	if ((revision & 0xf0) == 0x10) {
		udelay(2000);
		ty1208z_usb_phy_commands(controls[3], revision10, ARRAY_SIZE(revision10));
	} else {
		ty1208z_usb_phy_commands(controls[3], other_revision,
					ARRAY_SIZE(other_revision));
	}
	value = readl(controls[1]);
	writel(value & ~TY_USB_PHY_PORT_RESETS, controls[1]);
	udelay(2000);
	value = readl(controls[0]);
	writel((value & ~TY_USB_CONTROLLER_RESETS) | TY_USB_CONTROLLER_CLOCKS,
	       controls[0]);
	udelay(200);

	/* Fail before a generic HCD can touch its registers or start DMA. */
	if ((readl(controls[0]) & (TY_USB_CONTROLLER_RESETS | TY_USB_CONTROLLER_CLOCKS)) !=
	    TY_USB_CONTROLLER_CLOCKS ||
	    (readl(controls[1]) & (TY_USB_PHY_RESETS | 3U)) != 3U ||
	    (readl(controls[2]) & 0x209U) != 8U) {
		ty1208z_usb_host0_stop(controls);
		return -EIO;
	}
	return 0;
}
#endif
