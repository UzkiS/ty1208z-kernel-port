// SPDX-License-Identifier: GPL-2.0-only
/* Measured TY1208Z inherited PHY state; no PHY reset or frequency claim. */
#include <linux/clk-provider.h>
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include "ty1208z-ethernet-gate.h"

struct ty1208z_ethernet_clock {
	struct clk_hw hw;
	struct device *dev;
	void __iomem *control[5];
};

static int ty1208z_ethernet_prepare(struct clk_hw *hw)
{
	struct ty1208z_ethernet_clock *clock =
		container_of(hw, struct ty1208z_ethernet_clock, hw);
	int ret;

	ret = ty1208z_ethernet_gate_enable(clock->control);
	if (!ret)
		dev_info(clock->dev, "ETH_NET_CLOCK_ENABLED crg51=0000000b inherited-phy\n");
	return ret;
}

static void ty1208z_ethernet_unprepare(struct clk_hw *hw)
{
	struct ty1208z_ethernet_clock *clock =
		container_of(hw, struct ty1208z_ethernet_clock, hw);

	if (ty1208z_ethernet_gate_disable(clock->control[0]))
		dev_err(clock->dev, "ETH_NET_CLOCK_RESTORE_FAILED\n");
}

static const struct clk_ops ty1208z_ethernet_clock_ops = {
	.prepare = ty1208z_ethernet_prepare,
	.unprepare = ty1208z_ethernet_unprepare,
};

static int ty1208z_ethernet_clock_probe(struct platform_device *pdev)
{
	static const resource_size_t addresses[] = {
		0xf8a220cc, 0xf8a22120, 0xf8a20008, 0xf8a20118, 0xf8a20844,
	};
	struct device *dev = &pdev->dev;
	struct ty1208z_ethernet_clock *clock;
	struct clk_init_data init = {
		.name = "ty1208z-inherited-ethernet",
		.ops = &ty1208z_ethernet_clock_ops,
	};
	struct resource *res;
	unsigned int i;
	int ret;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic") &&
	    !of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-net") &&
	    !of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-router-ram") &&
	    !(IS_ENABLED(CONFIG_TY1208Z_ROUTER_RAM768) &&
	      of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-router768-ram")) &&
	    !(IS_ENABLED(CONFIG_TY1208Z_ROUTER_SD_RO) &&
	      of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-sdro-ram")) &&
	    !(IS_ENABLED(CONFIG_TY1208Z_ROUTER_EMMC_RO) &&
	      of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-emmcro-ram")))
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(addresses); i++) {
		res = platform_get_resource(pdev, IORESOURCE_MEM, i);
		if (!res || res->start != addresses[i] || resource_size(res) != 4)
			return -EINVAL;
	}
	if (platform_get_resource(pdev, IORESOURCE_MEM, ARRAY_SIZE(addresses)))
		return -EINVAL;
	clock = devm_kzalloc(dev, sizeof(*clock), GFP_KERNEL);
	if (!clock)
		return -ENOMEM;
	clock->dev = dev;
	for (i = 0; i < ARRAY_SIZE(addresses); i++) {
		clock->control[i] = devm_platform_ioremap_resource(pdev, i);
		if (IS_ERR(clock->control[i]))
			return PTR_ERR(clock->control[i]);
	}
	clock->hw.init = &init;
	ret = devm_clk_hw_register(dev, &clock->hw);
	if (ret)
		return ret;
	return devm_of_clk_add_hw_provider(dev, of_clk_hw_simple_get, &clock->hw);
}

static const struct of_device_id ty1208z_ethernet_clock_match[] = {
	{ .compatible = "tianyi,ty1208z-inherited-ethernet-clock" },
	{ }
};
MODULE_DEVICE_TABLE(of, ty1208z_ethernet_clock_match);

static struct platform_driver ty1208z_ethernet_clock_driver = {
	.probe = ty1208z_ethernet_clock_probe,
	.driver = {
		.name = "ty1208z-inherited-ethernet-clock",
		.of_match_table = ty1208z_ethernet_clock_match,
	},
};
module_platform_driver(ty1208z_ethernet_clock_driver);
MODULE_LICENSE("GPL");
