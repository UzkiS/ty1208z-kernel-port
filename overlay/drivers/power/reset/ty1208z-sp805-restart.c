// SPDX-License-Identifier: GPL-2.0-only
/* Opt-in RAM experiment: SP805 system restart without a watchdog device. */
#include <linux/delay.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/reboot.h>

#include "ty1208z-sp805-restart.h"

static int ty1208z_restart_callback(struct sys_off_data *data)
{
	if (!ty1208z_sp805_restart(data->cb_data)) {
		pr_err("TY1208Z_RESTART_REFUSED watchdog identity/state changed\n");
		return NOTIFY_DONE;
	}
	mdelay(1000);
	pr_err("TY1208Z_RESTART_TIMEOUT SP805 did not reset within one second\n");
	return NOTIFY_DONE;
}

static int ty1208z_restart_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct ty1208z_sp805_state state;
	struct resource *res;
	void __iomem *base;
	int ret;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic"))
		return -ENODEV;
	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!res || res->start != 0xf8a2c000 || resource_size(res) != 0x1000 ||
	    platform_get_resource(pdev, IORESOURCE_MEM, 1))
		return -EINVAL;
	base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(base))
		return PTR_ERR(base);
	ty1208z_sp805_observe(base, &state);
	dev_info(dev, "TY1208Z_RESTART_OBSERVED pid=%08x cid=%08x control=%08x\n",
		 state.peripheral_id, state.cell_id, state.control);
	if (!ty1208z_sp805_restart_ready(&state))
		return dev_err_probe(dev, -ENODEV, "Unexpected or active watchdog; no writes\n");
	ret = devm_register_sys_off_handler(dev, SYS_OFF_MODE_RESTART,
					   SYS_OFF_PRIO_DEFAULT, ty1208z_restart_callback, base);
	if (ret)
		return ret;
	dev_info(dev, "TY1208Z_RESTART_READY no-startup-writes explicit-restart-only\n");
	return 0;
}

static const struct of_device_id ty1208z_restart_match[] = {
	{ .compatible = "tianyi,ty1208z-sp805-restart" },
	{ }
};
MODULE_DEVICE_TABLE(of, ty1208z_restart_match);

static struct platform_driver ty1208z_restart_driver = {
	.probe = ty1208z_restart_probe,
	.driver = {
		.name = "ty1208z-sp805-restart",
		.of_match_table = ty1208z_restart_match,
	},
};
builtin_platform_driver(ty1208z_restart_driver);
MODULE_LICENSE("GPL");
