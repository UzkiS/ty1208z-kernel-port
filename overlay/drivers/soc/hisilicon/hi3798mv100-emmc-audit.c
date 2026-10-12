// SPDX-License-Identifier: GPL-2.0-only
/* Read-only controller identification before any MMC driver is enabled. */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

static int hi3798mv100_emmc_audit_probe(struct platform_device *pdev)
{
	static const unsigned int rates[] = { 75000000, 100000000,
					      50000000, 15000000 };
	static const struct {
		const char *name;
		u32 offset;
	} registers[] = {
		{ "CLKDIV", 0x08 }, { "CLKSRC", 0x0c }, { "CLKENA", 0x10 },
		{ "CTYPE", 0x18 }, { "FIFOTH", 0x4c }, { "USRID", 0x68 },
		{ "VERID", 0x6c }, { "HCON", 0x70 },
	};
	struct device *dev = &pdev->dev;
	void __iomem *controller, *crg;
	struct resource *res;
	u32 value;
	unsigned int i;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic"))
		return -ENODEV;
	/* Fixed measured resources; never expose arbitrary physical access. */
	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!res || res->start != 0xf9830000 || resource_size(res) != 0x1000)
		return -EINVAL;
	res = platform_get_resource(pdev, IORESOURCE_MEM, 1);
	if (!res || res->start != 0xf8a220a0 || resource_size(res) != 4)
		return -EINVAL;
	controller = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(controller))
		return PTR_ERR(controller);
	crg = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(crg))
		return PTR_ERR(crg);

	/* No FIFO/status reads, clock/reset changes or MMC commands. */
	for (i = 0; i < ARRAY_SIZE(registers); i++)
		dev_info(dev, "EMMC_AUDIT %s=%08x\n", registers[i].name,
			 readl(controller + registers[i].offset));
	value = readl(crg);
	dev_info(dev, "EMMC_AUDIT CRG40=%08x sdk_source_hz=%u\n",
		 value, rates[(value >> 8) & 3]);
	dev_info(dev, "EMMC_AUDIT_READ_ONLY_COMPLETE\n");
	return 0;
}

static const struct of_device_id hi3798mv100_emmc_audit_match[] = {
	{ .compatible = "tianyi,ty1208z-emmc-register-audit" },
	{ }
};
MODULE_DEVICE_TABLE(of, hi3798mv100_emmc_audit_match);

static struct platform_driver hi3798mv100_emmc_audit_driver = {
	.probe = hi3798mv100_emmc_audit_probe,
	.driver = {
		.name = "hi3798mv100-emmc-audit",
		.of_match_table = hi3798mv100_emmc_audit_match,
	},
};
builtin_platform_driver(hi3798mv100_emmc_audit_driver);
MODULE_LICENSE("GPL");
