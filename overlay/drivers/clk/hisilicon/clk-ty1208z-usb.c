// SPDX-License-Identifier: GPL-2.0-only
/* Optional host0 clock/PHY experiment; hardware USB audit remains pending. */
#include <linux/clk-provider.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include "ty1208z-usb-host0.h"

struct ty1208z_usb_clock {
	struct clk_hw hw;
	struct device *dev;
	void __iomem *controls[5];
};

static int ty1208z_usb_prepare(struct clk_hw *hw)
{
	struct ty1208z_usb_clock *clock = container_of(hw, struct ty1208z_usb_clock, hw);
	int ret = ty1208z_usb_host0_start(clock->controls);

	if (ret)
		dev_err(clock->dev, "USB_HOST0_PREPARE_FAILED error=%d\n", ret);
	else
		dev_info(clock->dev, "USB_HOST0_PREPARED sdk-host0-sequence\n");
	return ret;
}

static void ty1208z_usb_unprepare(struct clk_hw *hw)
{
	struct ty1208z_usb_clock *clock = container_of(hw, struct ty1208z_usb_clock, hw);

	if (ty1208z_usb_host0_stop(clock->controls))
		dev_err(clock->dev, "USB_HOST0_SHUTDOWN_READBACK_FAILED\n");
	else
		dev_info(clock->dev, "USB_HOST0_STOPPED last-ccf-user\n");
}

/*
 * One shared clock core, one provider output, two HCD consumers. The common
 * clock framework serializes prepare/unprepare and counts both consumers:
 * neither companion may reset the shared PHY while the other still owns it.
 * These operations must not be in atomic enable/disable callbacks.
 */
static const struct clk_ops ty1208z_usb_ops = {
	.prepare = ty1208z_usb_prepare,
	.unprepare = ty1208z_usb_unprepare,
};

static int ty1208z_usb_clock_probe(struct platform_device *pdev)
{
	static const resource_size_t addresses[] = {
		0xf8a220b8, 0xf8a220bc, 0xf8a20120, 0xf8a20124, 0xf8000ee0,
	};
	struct device *dev = &pdev->dev;
	struct ty1208z_usb_clock *clock;
	struct clk_init_data init = {
		.name = "ty1208z-usb-host0",
		.ops = &ty1208z_usb_ops,
	};
	struct resource *resource;
	unsigned int i;
	int ret;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-usb-host-experiment"))
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(addresses); i++) {
		resource = platform_get_resource(pdev, IORESOURCE_MEM, i);
		if (!resource || resource->start != addresses[i] || resource_size(resource) != 4)
			return -EINVAL;
	}
	if (platform_get_resource(pdev, IORESOURCE_MEM, ARRAY_SIZE(addresses)))
		return -EINVAL;
	clock = devm_kzalloc(dev, sizeof(*clock), GFP_KERNEL);
	if (!clock)
		return -ENOMEM;
	clock->dev = dev;
	for (i = 0; i < ARRAY_SIZE(addresses); i++) {
		clock->controls[i] = devm_platform_ioremap_resource(pdev, i);
		if (IS_ERR(clock->controls[i]))
			return PTR_ERR(clock->controls[i]);
	}
	if (!ty1208z_usb_revision_valid(readl(clock->controls[4])))
		return -ENODEV;
	/* Registering the provider performs no control writes. */
	clock->hw.init = &init;
	ret = devm_clk_hw_register(dev, &clock->hw);
	if (ret)
		return ret;
	return devm_of_clk_add_hw_provider(dev, of_clk_hw_simple_get, &clock->hw);
}

static const struct of_device_id ty1208z_usb_clock_match[] = {
	{ .compatible = "tianyi,ty1208z-usb-host0-clock" },
	{ }
};
MODULE_DEVICE_TABLE(of, ty1208z_usb_clock_match);

static struct platform_driver ty1208z_usb_clock_driver = {
	.probe = ty1208z_usb_clock_probe,
	.driver = {
		.name = "ty1208z-usb-host0-clock",
		.of_match_table = ty1208z_usb_clock_match,
	},
};
builtin_platform_driver(ty1208z_usb_clock_driver);
MODULE_LICENSE("GPL");
