// SPDX-License-Identifier: GPL-2.0-only
/* Observe the onboard SD controller without starting the MMC subsystem. */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

static int hi3798mv100_sd_audit_probe(struct platform_device *pdev)
{
	static const resource_size_t addresses[] = {
		0xf9820000, 0xf8a2209c, 0xf8a2011c,
	};
	static const resource_size_t sizes[] = { 0x1000, 4, 4 };
	static const unsigned int rates[] = {
		75000000, 100000000, 50000000, 15000000,
	};
	static const struct {
		const char *name;
		u32 offset;
	} registers[] = {
		{ "CLKDIV", 0x08 }, { "CLKSRC", 0x0c }, { "CLKENA", 0x10 },
		{ "CTYPE", 0x18 }, { "FIFOTH", 0x4c }, { "CDETECT", 0x50 },
		{ "WRTPRT", 0x54 }, { "USRID", 0x68 }, { "VERID", 0x6c },
		{ "HCON", 0x70 },
	};
	struct device *dev = &pdev->dev;
	struct resource *res;
	void __iomem *controller, *crg, *ldo;
	u32 value;
	unsigned int i;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic"))
		return -ENODEV;
	/* These are the original board FDT/SDK resources, not arbitrary MMIO. */
	for (i = 0; i < ARRAY_SIZE(addresses); i++) {
		res = platform_get_resource(pdev, IORESOURCE_MEM, i);
		if (!res || res->start != addresses[i] ||
		    resource_size(res) != sizes[i])
			return -EINVAL;
	}
	if (platform_get_resource(pdev, IORESOURCE_MEM, ARRAY_SIZE(addresses)))
		return -EINVAL;

	crg = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(crg))
		return PTR_ERR(crg);
	ldo = devm_platform_ioremap_resource(pdev, 2);
	if (IS_ERR(ldo))
		return PTR_ERR(ldo);
	value = readl(crg);
	dev_info(dev, "SD_AUDIT CRG39=%08x sdk_source_hz=%u\n",
		 value, rates[(value >> 8) & 3]);
	dev_info(dev, "SD_AUDIT LDO=%08x\n", readl(ldo));

	/* SDK clock enable sets bits 0/1 and deasserts reset bit 4. Leave an
	 * inactive controller untouched, including its register reads.
	 */
	if ((value & 0x13) != 0x03) {
		dev_info(dev, "SD_AUDIT_CONTROLLER_SKIPPED inactive-clock-or-reset\n");
	} else {
		controller = devm_platform_ioremap_resource(pdev, 0);
		if (IS_ERR(controller))
			return PTR_ERR(controller);
		/* No FIFO, IRQ/status, command, DMA, clock or regulator writes. */
		for (i = 0; i < ARRAY_SIZE(registers); i++)
			dev_info(dev, "SD_AUDIT %s=%08x\n", registers[i].name,
				 readl(controller + registers[i].offset));
		dev_info(dev, "SD_AUDIT_CONTROLLER_READ_COMPLETE\n");
	}
	dev_info(dev, "SD_AUDIT_READ_ONLY_COMPLETE no-card-commands no-control-writes\n");
	return 0;
}

static const struct of_device_id hi3798mv100_sd_audit_match[] = {
	{ .compatible = "tianyi,ty1208z-sd-register-audit" },
	{ }
};
MODULE_DEVICE_TABLE(of, hi3798mv100_sd_audit_match);

static struct platform_driver hi3798mv100_sd_audit_driver = {
	.probe = hi3798mv100_sd_audit_probe,
	.driver = {
		.name = "hi3798mv100-sd-audit",
		.of_match_table = hi3798mv100_sd_audit_match,
	},
};
builtin_platform_driver(hi3798mv100_sd_audit_driver);
MODULE_LICENSE("GPL");
