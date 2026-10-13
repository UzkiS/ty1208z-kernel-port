// SPDX-License-Identifier: GPL-2.0-only
/* One-shot guarded host0 clock/PHY initialization and capability observation. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include "ty1208z-usb-clock-audit.h"

static int hi3798mv100_usb_clock_audit_probe(struct platform_device *pdev)
{
	static const struct {
		resource_size_t address, size;
	} resources[] = {
		{ 0xf8a220b8, 4 }, { 0xf8a220bc, 4 },
		{ 0xf8a20120, 4 }, { 0xf8a20124, 4 }, { 0xf8000ee0, 4 },
		{ 0xf9890000, 0x10000 }, { 0xf9880000, 0x10000 },
	};
	struct device *dev = &pdev->dev;
	void __iomem *mapped[ARRAY_SIZE(resources)];
	struct ty1208z_usb_clock_result result;
	struct resource *res;
	unsigned int i;
	int ret;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-usb-clock-audit"))
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
	ret = ty1208z_usb_clock_audit(mapped, mapped[5], mapped[6], &result);
	dev_info(dev, "USB_CLOCK_AUDIT_BEFORE CRG46=%08x CRG47=%08x USB0=%08x USB1=%08x SYSID0=%08x changed=%u\n",
		 result.before.crg46, result.before.crg47, result.before.usb0,
		 result.before.usb1, result.before.sysid0, result.changed);
	if (result.enabled.controller_read)
		dev_info(dev, "USB_CLOCK_AUDIT_CAPS EHCI_CAPBASE=%08x HCSPARAMS=%08x HCCPARAMS=%08x OHCI_REVISION=%08x\n",
			 result.enabled.ehci_capbase, result.enabled.ehci_hcsparams,
			 result.enabled.ehci_hccparams, result.enabled.ohci_revision);
	dev_info(dev, "USB_CLOCK_AUDIT_STOP CRG46=%08x CRG47=%08x USB0=%08x USB1=%08x error=%d\n",
		 result.stopped.crg46, result.stopped.crg47, result.stopped.usb0,
		 result.stopped.usb1, result.stop_error);
	if (ret) {
		dev_warn(dev, "USB_CLOCK_AUDIT_FAILED error=%d\n", ret);
		return ret;
	}
	dev_info(dev, "USB_CLOCK_AUDIT_COMPLETE sdk-last-user-stop no-device-transactions no-dma no-firmware\n");
	return 0;
}

static const struct of_device_id hi3798mv100_usb_clock_audit_match[] = {
	{ .compatible = "tianyi,ty1208z-usb-clock-capability-audit" },
	{ }
};
MODULE_DEVICE_TABLE(of, hi3798mv100_usb_clock_audit_match);

static struct platform_driver hi3798mv100_usb_clock_audit_driver = {
	.probe = hi3798mv100_usb_clock_audit_probe,
	.driver = {
		.name = "hi3798mv100-usb-clock-audit",
		.of_match_table = hi3798mv100_usb_clock_audit_match,
	},
};
builtin_platform_driver(hi3798mv100_usb_clock_audit_driver);
MODULE_LICENSE("GPL");
