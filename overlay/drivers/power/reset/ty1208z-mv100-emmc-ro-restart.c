// SPDX-License-Identifier: GPL-2.0-only
/* Explicit measured reset only after the independent eMMC host is stopped. */
#include <linux/delay.h>
#include <linux/bitops.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/reboot.h>
#include <linux/slab.h>

#include "ty1208z-mv100-restart.h"

struct ty1208z_emmc_ro_restart_context {
	void __iomem *base;
	void __iomem *sysid;
	void __iomem *controller;
	void __iomem *crg;
};

static bool ty1208z_emmc_ro_identity(struct ty1208z_emmc_ro_restart_context *c)
{
	return readl(c->crg) == 0x00040103 &&
		readl(c->controller + 0x6c) == 0x5342270a &&
		readl(c->controller + 0x70) == 0x00e44c81;
}

static int ty1208z_emmc_ro_restart_callback(struct sys_off_data *data)
{
	struct ty1208z_emmc_ro_restart_context *c = data->cb_data;

	/* Repeat controller identity and quiescence checks at restart time.
	 * A failed shutdown must never arm the reset watchdog.
	 */
	if (!ty1208z_emmc_ro_identity(c) || readl(c->controller + 0x24) ||
	    readl(c->controller + 0x10) || readl(c->controller + 0x90) ||
	    (readl(c->controller) & (BIT(5) | BIT(25)))) {
		pr_err("EMMC_RO_RESTART_REFUSED controller-not-quiesced\n");
		return NOTIFY_DONE;
	}
	if (!ty1208z_mv100_restart(c->base, c->sysid)) {
		pr_err("TY1208Z_RESTART_REFUSED watchdog identity/state changed\n");
		return NOTIFY_DONE;
	}
	mdelay(1000);
	pr_err("TY1208Z_RESTART_TIMEOUT SP805 did not reset within one second\n");
	return NOTIFY_DONE;
}

static int ty1208z_emmc_ro_restart_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct ty1208z_emmc_ro_restart_context *c;
	struct resource *res;
	static const resource_size_t starts[] = {
		0xf8a2c000, 0xf8000ee0, 0xf9830000, 0xf8a220a0,
	};
	static const resource_size_t sizes[] = { 0x1000, 4, 0x1000, 4 };
	unsigned int i;
	int ret;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-emmc-ro-ram"))
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(starts); i++) {
		res = platform_get_resource(pdev, IORESOURCE_MEM, i);
		if (!res || res->start != starts[i] || resource_size(res) != sizes[i])
			return -EINVAL;
	}
	if (platform_get_resource(pdev, IORESOURCE_MEM, i))
		return -EINVAL;
	c = devm_kzalloc(dev, sizeof(*c), GFP_KERNEL);
	if (!c)
		return -ENOMEM;
	c->sysid = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(c->sysid))
		return PTR_ERR(c->sysid);
	c->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(c->base))
		return PTR_ERR(c->base);
	/* The eMMC driver owns these exact resources. Observe them without a
	 * second exclusive reservation; this driver never writes either mapping.
	 */
	c->crg = devm_ioremap(dev, starts[3], sizes[3]);
	if (!c->crg)
		return -ENOMEM;
	c->controller = devm_ioremap(dev, starts[2], sizes[2]);
	if (!c->controller)
		return -ENOMEM;
	if (!ty1208z_mv100_restart_ready(c->base, c->sysid) ||
	    !ty1208z_emmc_ro_identity(c))
		return dev_err_probe(dev, -ENODEV, "Unexpected watchdog/eMMC identity; no writes\n");
	ret = devm_register_sys_off_handler(dev, SYS_OFF_MODE_RESTART,
		SYS_OFF_PRIO_DEFAULT, ty1208z_emmc_ro_restart_callback, c);
	if (ret)
		return ret;
	dev_info(dev, "TY1208Z_MV100_RESTART_READY sysid=37980100 measured-inactive-watchdog no-startup-writes\n");
	dev_info(dev, "TY1208Z_RESTART_READY no-startup-writes explicit-restart-only\n");
	return 0;
}

static const struct of_device_id ty1208z_emmc_ro_restart_match[] = {
	{ .compatible = "tianyi,ty1208z-mv100-emmc-ro-restart" },
	{ }
};
MODULE_DEVICE_TABLE(of, ty1208z_emmc_ro_restart_match);

static struct platform_driver ty1208z_emmc_ro_restart_driver = {
	.probe = ty1208z_emmc_ro_restart_probe,
	.driver = {
		.name = "ty1208z-mv100-emmc-ro-restart",
		.of_match_table = ty1208z_emmc_ro_restart_match,
	},
};
builtin_platform_driver(ty1208z_emmc_ro_restart_driver);
MODULE_LICENSE("GPL");
