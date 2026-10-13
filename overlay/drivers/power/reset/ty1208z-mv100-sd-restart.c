// SPDX-License-Identifier: GPL-2.0-only
/* Explicit reset for the separate, storage-disabled SD identification profile. */
#include <linux/delay.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/reboot.h>
#include <linux/slab.h>

#include "ty1208z-mv100-restart.h"

struct ty1208z_sd_restart_context {
	void __iomem *base;
	void __iomem *sysid;
};

static int ty1208z_sd_restart_callback(struct sys_off_data *data)
{
	struct ty1208z_sd_restart_context *context = data->cb_data;

	if (!ty1208z_mv100_restart(context->base, context->sysid)) {
		pr_err("TY1208Z_RESTART_REFUSED watchdog identity/state changed\n");
		return NOTIFY_DONE;
	}
	mdelay(1000);
	pr_err("TY1208Z_RESTART_TIMEOUT SP805 did not reset within one second\n");
	return NOTIFY_DONE;
}

static int ty1208z_sd_restart_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct ty1208z_sd_restart_context *context;
	struct resource *res;
	int ret;

	if (IS_ENABLED(CONFIG_HI3798MV100_SD_READ_ONLY) ?
	    !of_machine_is_compatible("tianyi,ty1208z-ca-sd-ro-ram") :
	    !of_machine_is_compatible("tianyi,ty1208z-ca-sd-ident-ram"))
		return -ENODEV;
	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!res || res->start != 0xf8a2c000 || resource_size(res) != 0x1000)
		return -EINVAL;
	res = platform_get_resource(pdev, IORESOURCE_MEM, 1);
	if (!res || res->start != 0xf8000ee0 || resource_size(res) != 4 ||
	    platform_get_resource(pdev, IORESOURCE_MEM, 2))
		return -EINVAL;
	context = devm_kzalloc(dev, sizeof(*context), GFP_KERNEL);
	if (!context)
		return -ENOMEM;
	context->sysid = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(context->sysid))
		return PTR_ERR(context->sysid);
	context->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(context->base))
		return PTR_ERR(context->base);
	if (!ty1208z_mv100_restart_ready(context->base, context->sysid))
		return dev_err_probe(dev, -ENODEV, "Unexpected MV100 identity/watchdog state; no writes\n");
	ret = devm_register_sys_off_handler(dev, SYS_OFF_MODE_RESTART,
		SYS_OFF_PRIO_DEFAULT, ty1208z_sd_restart_callback, context);
	if (ret)
		return ret;
	dev_info(dev, "TY1208Z_MV100_RESTART_READY sysid=37980100 measured-inactive-watchdog no-startup-writes\n");
	dev_info(dev, "TY1208Z_RESTART_READY no-startup-writes explicit-restart-only\n");
	return 0;
}

static const struct of_device_id ty1208z_sd_restart_match[] = {
	{ .compatible = "tianyi,ty1208z-mv100-sd-ident-restart" },
	{ }
};
MODULE_DEVICE_TABLE(of, ty1208z_sd_restart_match);

static struct platform_driver ty1208z_sd_restart_driver = {
	.probe = ty1208z_sd_restart_probe,
	.driver = {
		.name = "ty1208z-mv100-sd-restart",
		.of_match_table = ty1208z_sd_restart_match,
	},
};
builtin_platform_driver(ty1208z_sd_restart_driver);
MODULE_LICENSE("GPL");
