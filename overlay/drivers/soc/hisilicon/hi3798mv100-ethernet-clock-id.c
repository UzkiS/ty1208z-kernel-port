// SPDX-License-Identifier: GPL-2.0-only
/* Guarded volatile MAC clock enable and PHY-ID read; restore the clock. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include "ty1208z-ethernet-clock-id.h"

static int hi3798mv100_ethernet_clock_id_probe(struct platform_device *pdev)
{
	static const struct {
		resource_size_t address;
		resource_size_t size;
		const char *name;
	} resources[] = {
		{ 0xf9841100, 8, "MDIO" },
		{ 0xf8a220cc, 4, "CRG51" },
		{ 0xf8a22120, 4, "PHY_CRG" },
		{ 0xf8a20008, 4, "PHY_SELECT" },
		{ 0xf8a20118, 4, "PHY_ADDRESS" },
		{ 0xf8a20844, 4, "PHY_LDO" },
	};
	struct device *dev = &pdev->dev;
	void __iomem *mapped[ARRAY_SIZE(resources)];
	u32 values[ARRAY_SIZE(resources)] = { 0 };
	struct ty1208z_eth_clock_result result;
	struct resource *res;
	unsigned int i;
	int ret;

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
	for (i = 1; i < ARRAY_SIZE(resources); i++) {
		values[i] = readl(mapped[i]);
		dev_info(dev, "ETH_CLOCK_ID %s=%08x\n", resources[i].name, values[i]);
	}
	ret = ty1208z_eth_clock_id(mapped[1], mapped[0], values[2], values[3],
				 values[4], values[5], &result);
	dev_info(dev, "ETH_CLOCK_ID_STATE before=%08x enabled=%08x restored=%08x changed=%u verified=%u\n",
		 result.before, result.enabled, result.restored, result.changed,
		 result.restore_verified);
	if (ret) {
		dev_warn(dev, "ETH_CLOCK_ID_FAILED error=%d\n", ret);
		return ret;
	}
	dev_info(dev, "ETH_CLOCK_ID_PHY_ID=%08x addr=1\n", result.phy_id);
	dev_info(dev, "ETH_CLOCK_ID_COMPLETE clock-restored no-phy-reset-writes no-dma\n");
	return 0;
}

static const struct of_device_id hi3798mv100_ethernet_clock_id_match[] = {
	{ .compatible = "tianyi,ty1208z-ethernet-clock-id" },
	{ }
};
MODULE_DEVICE_TABLE(of, hi3798mv100_ethernet_clock_id_match);

static struct platform_driver hi3798mv100_ethernet_clock_id_driver = {
	.probe = hi3798mv100_ethernet_clock_id_probe,
	.driver = {
		.name = "hi3798mv100-ethernet-clock-id",
		.of_match_table = hi3798mv100_ethernet_clock_id_match,
	},
};
module_platform_driver(hi3798mv100_ethernet_clock_id_driver);
MODULE_DESCRIPTION("TY1208Z guarded temporary MAC clock and PHY-ID experiment");
MODULE_LICENSE("GPL");
