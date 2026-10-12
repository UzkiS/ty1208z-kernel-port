// SPDX-License-Identifier: GPL-2.0-only
/* Observe inherited Ethernet state; never initialize MAC, clocks or PHY. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include "ty1208z-ethernet-audit.h"

static int hi3798mv100_ethernet_audit_probe(struct platform_device *pdev)
{
	static const struct {
		resource_size_t address;
		resource_size_t size;
		const char *name;
	} resources[] = {
		{ 0xf9840000, 0x4000, "MAC" },
		{ 0xf8a220cc, 4, "CRG51" },
		{ 0xf8a22120, 4, "PHY_CRG" },
		{ 0xf8a20008, 4, "PHY_SELECT" },
		{ 0xf8a20118, 4, "PHY_ADDRESS" },
		{ 0xf8a20844, 4, "PHY_LDO" },
	};
	static const struct {
		const char *name;
		u32 offset;
	} registers[] = {
		{ "PORT_MODE", 0x200 }, { "PORT_STATUS", 0x208 },
		{ "QUEUE_CONFIG", 0x344 }, { "QUEUE_STATUS", 0x36c },
		{ "SOFT_RESET", 0x1308 }, { "FWCTRL", 0x1310 },
		{ "IRQ_STATUS", 0x1330 }, { "IRQ_ENABLE", 0x1334 },
		{ "IRQ_RAW", 0x1338 }, { "MDIO_CONTROL", 0x1100 },
	};
	struct device *dev = &pdev->dev;
	void __iomem *mapped[ARRAY_SIZE(resources)];
	u32 values[ARRAY_SIZE(resources)] = { 0 }, phy_id;
	struct resource *res;
	unsigned int i;
	int ret;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic"))
		return -ENODEV;
	/* Reject any changed resource before mapping or touching the hardware. */
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
	/* Control registers are observed before any access to the clocked MAC. */
	for (i = 1; i < ARRAY_SIZE(resources); i++) {
		values[i] = readl(mapped[i]);
		dev_info(dev, "ETH_AUDIT %s=%08x\n", resources[i].name, values[i]);
	}
	if (!ty1208z_eth_inherited_ready(values[1], values[2], values[3], values[4])) {
		dev_info(dev, "ETH_AUDIT_MDIO_SKIPPED inherited-state-not-ready\n");
		goto complete;
	}
	/* No MAC address, FIFO/descriptors, read-to-clear PHY status or IRQ writes. */
	for (i = 0; i < ARRAY_SIZE(registers); i++)
		dev_info(dev, "ETH_AUDIT %s=%08x\n", registers[i].name,
			 readl(mapped[0] + registers[i].offset));
	ret = ty1208z_eth_read_phy_id(mapped[0] + 0x1100, &phy_id);
	if (ret)
		dev_info(dev, "ETH_AUDIT_PHY_ID_UNAVAILABLE error=%d\n", ret);
	else
		dev_info(dev, "ETH_AUDIT_PHY_ID addr=1 id=%08x\n", phy_id);
complete:
	dev_info(dev, "ETH_AUDIT_COMPLETE no-phy-writes no-clock-reset-writes no-dma\n");
	return 0;
}

static const struct of_device_id hi3798mv100_ethernet_audit_match[] = {
	{ .compatible = "tianyi,ty1208z-ethernet-audit" },
	{ }
};
MODULE_DEVICE_TABLE(of, hi3798mv100_ethernet_audit_match);

static struct platform_driver hi3798mv100_ethernet_audit_driver = {
	.probe = hi3798mv100_ethernet_audit_probe,
	.driver = {
		.name = "hi3798mv100-ethernet-audit",
		.of_match_table = hi3798mv100_ethernet_audit_match,
	},
};
builtin_platform_driver(hi3798mv100_ethernet_audit_driver);
MODULE_LICENSE("GPL");
