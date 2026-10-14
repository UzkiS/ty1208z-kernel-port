// SPDX-License-Identifier: GPL-2.0-only
/* Guard the measured reset after both native read-only hosts shut down. */
#include <linux/bitops.h>
#include <linux/delay.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/reboot.h>
#include <linux/slab.h>
#include "ty1208z-mv100-restart.h"

struct ty1208z_system_reset {
	void __iomem *base;
	void __iomem *sysid;
	void __iomem *host[2];
};

static bool ty1208z_system_host_ready(void __iomem *host, bool shutdown)
{
	if (readl(host + 0x6c) != 0x5342270a || readl(host + 0x70) != 0x00e44c81)
		return false;
	return !shutdown || (!readl(host + 0x24) && !readl(host + 0x10) &&
		!readl(host + 0x90) && !(readl(host) & (BIT(5) | BIT(25))));
}

static int ty1208z_system_restart(struct sys_off_data *data)
{
	struct ty1208z_system_reset *c = data->cb_data;

	if (!ty1208z_system_host_ready(c->host[0], true) ||
	    !ty1208z_system_host_ready(c->host[1], true)) {
		pr_err("TY1208Z_SYSTEM_RESTART_REFUSED storage-not-quiesced\n");
		return NOTIFY_DONE;
	}
	pr_info("TY1208Z_SYSTEM_STORAGE_SHUTDOWN_PASS emmc-and-sd\n");
	if (!ty1208z_mv100_restart(c->base, c->sysid)) {
		pr_err("TY1208Z_SYSTEM_RESTART_REFUSED watchdog-state\n");
		return NOTIFY_DONE;
	}
	mdelay(1000);
	pr_err("TY1208Z_SYSTEM_RESTART_TIMEOUT\n");
	return NOTIFY_DONE;
}

static int ty1208z_system_reset_probe(struct platform_device *pdev)
{
	static const resource_size_t starts[] = {0xf8a2c000, 0xf8000ee0,
		0xf9830000, 0xf9820000};
	static const resource_size_t sizes[] = {0x1000, 4, 0x1000, 0x1000};
	struct ty1208z_system_reset *c;
	struct resource *res;
	unsigned int i;
	int ret;

	if (!IS_ENABLED(CONFIG_TY1208Z_OPENWRT_SYSTEM) ||
	    !of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-system-ram"))
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(starts); i++) {
		res = platform_get_resource(pdev, IORESOURCE_MEM, i);
		if (!res || res->start != starts[i] || resource_size(res) != sizes[i])
			return -EINVAL;
	}
	if (platform_get_resource(pdev, IORESOURCE_MEM, i))
		return -EINVAL;
	c = devm_kzalloc(&pdev->dev, sizeof(*c), GFP_KERNEL);
	if (!c)
		return -ENOMEM;
	c->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(c->base))
		return PTR_ERR(c->base);
	c->sysid = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(c->sysid))
		return PTR_ERR(c->sysid);
	/* Each MMC driver owns its controller; reset only observes it. */
	for (i = 0; i < 2; i++) {
		c->host[i] = devm_ioremap(&pdev->dev, starts[i + 2], sizes[i + 2]);
		if (!c->host[i] || !ty1208z_system_host_ready(c->host[i], false))
			return -ENODEV;
	}
	if (!ty1208z_mv100_restart_ready(c->base, c->sysid))
		return -ENODEV;
	ret = devm_register_sys_off_handler(&pdev->dev, SYS_OFF_MODE_RESTART,
		SYS_OFF_PRIO_DEFAULT, ty1208z_system_restart, c);
	if (!ret)
		dev_info(&pdev->dev, "TY1208Z_SYSTEM_RESTART_READY no-startup-writes\n");
	return ret;
}

static const struct of_device_id ty1208z_system_reset_match[] = {
	{ .compatible = "tianyi,ty1208z-mv100-system-restart" }, { }
};
MODULE_DEVICE_TABLE(of, ty1208z_system_reset_match);
static struct platform_driver ty1208z_system_reset_driver = {
	.probe = ty1208z_system_reset_probe,
	.driver = { .name = "ty1208z-mv100-system-restart",
		.of_match_table = ty1208z_system_reset_match },
};
module_platform_driver(ty1208z_system_reset_driver);
MODULE_LICENSE("GPL");
