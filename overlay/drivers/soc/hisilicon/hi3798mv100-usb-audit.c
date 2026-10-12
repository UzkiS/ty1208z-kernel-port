// SPDX-License-Identifier: GPL-2.0-only
/* Read-only host0 USB clocks/revision/capabilities before enabling USB. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include "ty1208z-usb-audit.h"

static int hi3798mv100_usb_audit_probe(struct platform_device *pdev)
{
	static const struct {
		resource_size_t address;
		resource_size_t size;
	} resources[] = {
		{ 0xf8a220b8, 4 }, { 0xf8a220bc, 4 },
		{ 0xf8a20120, 4 }, { 0xf8a20124, 4 }, { 0xf8000ee0, 4 },
		{ 0xf9890000, 0x10000 }, { 0xf9880000, 0x10000 },
	};
	struct device *dev = &pdev->dev;
	void __iomem *mapped[ARRAY_SIZE(resources)];
	struct ty1208z_usb_snapshot state = { 0 };
	struct resource *res;
	unsigned int i;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic"))
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(resources); i++) {
		res = platform_get_resource(pdev, IORESOURCE_MEM, i);
		if (!res || res->start != resources[i].address ||
		    resource_size(res) != resources[i].size)
			return -EINVAL;
	}
	if (platform_get_resource(pdev, IORESOURCE_MEM, ARRAY_SIZE(resources)))
		return -EINVAL;
	for (i = 0; i < ARRAY_SIZE(resources); i++) {
		mapped[i] = devm_platform_ioremap_resource(pdev, i);
		if (IS_ERR(mapped[i]))
			return PTR_ERR(mapped[i]);
	}
	ty1208z_usb_observe(mapped, mapped[5], mapped[6], &state);
	dev_info(dev, "USB_AUDIT CRG46=%08x CRG47=%08x\n", state.crg46, state.crg47);
	dev_info(dev, "USB_AUDIT USB0=%08x USB1=%08x SYSID0=%08x revision_branch=%s\n",
		 state.usb0, state.usb1, state.sysid0,
		 (state.sysid0 & 0xf0) == 0x10 ? "sdk-10" : "sdk-other");
	if (state.controller_read)
		dev_info(dev, "USB_AUDIT EHCI_CAPBASE=%08x HCSPARAMS=%08x HCCPARAMS=%08x OHCI_REVISION=%08x\n",
			 state.ehci_capbase, state.ehci_hcsparams,
			 state.ehci_hccparams, state.ohci_revision);
	else
		dev_info(dev, "USB_AUDIT_CAPABILITIES_SKIPPED inherited-state-not-ready\n");
	dev_info(dev, "USB_AUDIT_READ_ONLY_COMPLETE no-clock-reset-writes no-device-transactions\n");
	return 0;
}

static const struct of_device_id hi3798mv100_usb_audit_match[] = {
	{ .compatible = "tianyi,ty1208z-usb-register-audit" },
	{ }
};
MODULE_DEVICE_TABLE(of, hi3798mv100_usb_audit_match);

static struct platform_driver hi3798mv100_usb_audit_driver = {
	.probe = hi3798mv100_usb_audit_probe,
	.driver = {
		.name = "hi3798mv100-usb-audit",
		.of_match_table = hi3798mv100_usb_audit_match,
	},
};
builtin_platform_driver(hi3798mv100_usb_audit_driver);
MODULE_LICENSE("GPL");
