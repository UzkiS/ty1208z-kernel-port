/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef TY1208Z_USB_CLOCK_AUDIT_H
#define TY1208Z_USB_CLOCK_AUDIT_H

#include "ty1208z-usb-audit.h"
#include "../../clk/hisilicon/ty1208z-usb-host0.h"

struct ty1208z_usb_clock_result {
	struct ty1208z_usb_snapshot before, enabled, stopped;
	bool changed;
	int stop_error;
};

static inline void ty1208z_usb_clock_controls(void __iomem *control[5],
		struct ty1208z_usb_snapshot *state)
{
	state->crg46 = readl(control[0]);
	state->crg47 = readl(control[1]);
	state->usb0 = readl(control[2]);
	state->usb1 = readl(control[3]);
	state->sysid0 = readl(control[4]);
}

/* Only the exact inactive state measured by the physical read-only audit. */
static inline bool ty1208z_usb_clock_initial(const struct ty1208z_usb_snapshot *s)
{
	return s->crg46 == 0x0013707f && s->crg47 == 0x00000b01 &&
	       s->usb0 == 0x000c71a8 && s->usb1 == 0 &&
	       s->sysid0 == 0x37980100;
}

static inline bool ty1208z_usb_capabilities_sane(const struct ty1208z_usb_snapshot *s)
{
	u32 length = s->ehci_capbase & 0xff;
	u32 ports = s->ehci_hcsparams & 0xf;
	u32 ohci_version = s->ohci_revision & 0xff;

	/* Structural EHCI/OHCI checks; raw capabilities are retained for review. */
	return s->controller_read && length >= 0x10 && length <= 0x80 &&
	       !(length & 3) && (s->ehci_capbase >> 16) == 0x0100 &&
	       ports && s->ehci_hcsparams != ~0U && s->ehci_hccparams != ~0U &&
	       s->ohci_revision != ~0U &&
	       (ohci_version == 0x10 || ohci_version == 0x11);
}

/* No HCD, operational-register, schedule, endpoint or firmware access.
 * The fixed SDK-equivalent sequence programs volatile analog PHY controls.
 * Shutdown is the SDK last-user stop, NOT restoration of analog tuning.
 */
static inline int ty1208z_usb_clock_audit(void __iomem *control[5],
		void __iomem *ehci, void __iomem *ohci,
		struct ty1208z_usb_clock_result *result)
{
	int ret;

	*result = (struct ty1208z_usb_clock_result) { 0 };
	ty1208z_usb_clock_controls(control, &result->before);
	if (!ty1208z_usb_clock_initial(&result->before))
		return -ENODEV;
	result->changed = true;
	ret = ty1208z_usb_host0_start(control);
	if (!ret) {
		ty1208z_usb_observe(control, ehci, ohci, &result->enabled);
		if (!ty1208z_usb_capabilities_sane(&result->enabled))
			ret = -EIO;
	}
	/* Also independently verify stop after a failed initialization. */
	result->stop_error = ty1208z_usb_host0_stop(control);
	/* Read controls only: no controller capability reads after stopping. */
	ty1208z_usb_clock_controls(control, &result->stopped);
	if (result->stop_error || result->stopped.controller_read ||
	    (result->stopped.crg47 & TY_USB_PHY_RESETS) != TY_USB_PHY_RESETS ||
	    (result->stopped.crg46 & 0x71U))
		return -EIO;
	return ret;
}
#endif
