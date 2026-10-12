/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef TY1208Z_USB_AUDIT_H
#define TY1208Z_USB_AUDIT_H

#include <linux/bitops.h>
#include <linux/io.h>
#include <linux/types.h>

struct ty1208z_usb_snapshot {
	u32 crg46, crg47, usb0, usb1, sysid0;
	u32 ehci_capbase, ehci_hcsparams, ehci_hccparams, ohci_revision;
	bool controller_read;
};

/* SDK readiness conditions only: this never enables clocks or resets PHYs.
 * Both host0 ports and the companion share these controls. SYSID0 supplies
 * the low-byte revision branch; the SOC_FUSE register is not needed here.
 */
static inline bool ty1208z_usb_inherited_ready(u32 crg46, u32 crg47,
					    u32 usb0, u32 sysid0)
{
	u32 clock_mask = GENMASK(6, 0);
	u32 reset_mask = GENMASK(14, 12) | BIT(16) | BIT(17);
	u32 phy_reset_mask = GENMASK(11, 8);

	return sysid0 && sysid0 != ~0U &&
		(crg46 & (clock_mask | reset_mask)) == clock_mask &&
		(crg47 & (GENMASK(1, 0) | phy_reset_mask)) == GENMASK(1, 0) &&
		(usb0 & (BIT(0) | BIT(3) | BIT(9))) == BIT(3);
}

static inline void ty1208z_usb_observe(void __iomem *control[5],
				     void __iomem *ehci, void __iomem *ohci,
				     struct ty1208z_usb_snapshot *state)
{
	state->crg46 = readl(control[0]);
	state->crg47 = readl(control[1]);
	state->usb0 = readl(control[2]);
	state->usb1 = readl(control[3]);
	state->sysid0 = readl(control[4]);
	state->controller_read = false;
	if (!ty1208z_usb_inherited_ready(state->crg46, state->crg47,
					state->usb0, state->sysid0))
		return;
	/* Fixed read-only capability words. No operational registers, PORTSC,
	 * schedule/FIFO pointers, IRQ acknowledgements or device transactions.
	 */
	state->ehci_capbase = readl(ehci);
	state->ehci_hcsparams = readl(ehci + 4);
	state->ehci_hccparams = readl(ehci + 8);
	state->ohci_revision = readl(ohci);
	state->controller_read = true;
}

#endif
