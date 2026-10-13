// SPDX-License-Identifier: GPL-2.0-only
/* Opt-in RAM experiment: SP805 system restart without a watchdog device. */
#include <linux/delay.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/reboot.h>

#include "ty1208z-sp805-restart.h"
#ifdef TY1208Z_RAM_RESTART_MODULE
#include <linux/slab.h>
#include "ty1208z-mv100-restart.h"

struct ty1208z_ram_restart_context {
	void __iomem *base;
	void __iomem *sysid;
};
#endif

static int ty1208z_restart_callback(struct sys_off_data *data)
{
#ifdef TY1208Z_RAM_RESTART_MODULE
	struct ty1208z_ram_restart_context *context = data->cb_data;

	if (!ty1208z_mv100_restart(context->base, context->sysid)) {
#else
	if (!ty1208z_sp805_restart(data->cb_data)) {
#endif
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
#ifdef TY1208Z_RAM_RESTART_MODULE
	struct ty1208z_ram_restart_context *context;
#endif

#ifdef TY1208Z_RAM_RESTART_MODULE
	if (!of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-router-ram") &&
	    !(IS_ENABLED(CONFIG_TY1208Z_ROUTER_RAM768) &&
	      of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-router768-ram")) &&
	    !(IS_ENABLED(CONFIG_TY1208Z_ROUTER_SD_RO) &&
	      of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-sdro-ram")))
#else
	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic"))
#endif
		return -ENODEV;
	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!res || res->start != 0xf8a2c000 || resource_size(res) != 0x1000)
		return -EINVAL;
#ifdef TY1208Z_RAM_RESTART_MODULE
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
#else
	if (platform_get_resource(pdev, IORESOURCE_MEM, 1))
		return -EINVAL;
#endif
	base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(base))
		return PTR_ERR(base);
	ty1208z_sp805_observe(base, &state);
	dev_info(dev, "TY1208Z_RESTART_OBSERVED pid=%08x cid=%08x control=%08x\n",
		 state.peripheral_id, state.cell_id, state.control);
#ifdef TY1208Z_RAM_RESTART_MODULE
	dev_info(dev, "TY1208Z_RESTART_REGISTERS load=%08x value=%08x ris=%08x mis=%08x lock=%08x\n",
		 readl(base), readl(base + 0x004), readl(base + 0x010),
		 readl(base + 0x014), readl(base + 0xc00));
	if (!ty1208z_mv100_restart_ready(base, context->sysid))
		return dev_err_probe(dev, -ENODEV, "Unexpected MV100 identity/watchdog state; no writes\n");
	context->base = base;
	ret = devm_register_sys_off_handler(dev, SYS_OFF_MODE_RESTART,
		SYS_OFF_PRIO_DEFAULT, ty1208z_restart_callback, context);
#else
	if (!ty1208z_sp805_restart_ready(&state))
		return dev_err_probe(dev, -ENODEV, "Unexpected or active watchdog; no writes\n");
	ret = devm_register_sys_off_handler(dev, SYS_OFF_MODE_RESTART,
					   SYS_OFF_PRIO_DEFAULT, ty1208z_restart_callback, base);
#endif
	if (ret)
		return ret;
	platform_set_drvdata(pdev, base);
#ifdef TY1208Z_RAM_RESTART_MODULE
	dev_info(dev, "TY1208Z_MV100_RESTART_READY sysid=37980100 measured-inactive-watchdog no-startup-writes\n");
#endif
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
#ifdef TY1208Z_RAM_RESTART_MODULE
/* An explicit RAM-loaded module can supply the missing restart handler to
 * the exact native router without changing its live DT or persistent boot.
 * Probe checks measured MV100 identity and inactive watchdog state before binding.
 */
static struct platform_device *ty1208z_restart_device;

static int __init ty1208z_ram_restart_init(void)
{
	static const struct resource resources[] = {
		{
			.start = 0xf8a2c000,
			.end = 0xf8a2cfff,
			.flags = IORESOURCE_MEM,
		}, {
			.start = 0xf8000ee0,
			.end = 0xf8000ee3,
			.flags = IORESOURCE_MEM,
		},
	};
	int ret;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-router-ram") &&
	    !(IS_ENABLED(CONFIG_TY1208Z_ROUTER_RAM768) &&
	      of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-router768-ram")) &&
	    !(IS_ENABLED(CONFIG_TY1208Z_ROUTER_SD_RO) &&
	      of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-sdro-ram")))
		return -ENODEV;
	ret = platform_driver_register(&ty1208z_restart_driver);
	if (ret)
		return ret;
	ty1208z_restart_device = platform_device_register_simple(
		"ty1208z-sp805-restart", -1, resources, ARRAY_SIZE(resources));
	if (IS_ERR(ty1208z_restart_device)) {
		ret = PTR_ERR(ty1208z_restart_device);
		goto unregister_driver;
	}
	/* Device registration alone does not propagate a failed probe. */
	if (!platform_get_drvdata(ty1208z_restart_device)) {
		platform_device_unregister(ty1208z_restart_device);
		ret = -ENODEV;
		goto unregister_driver;
	}
	return 0;

unregister_driver:
	platform_driver_unregister(&ty1208z_restart_driver);
	return ret;
}
module_init(ty1208z_ram_restart_init);

static void __exit ty1208z_ram_restart_exit(void)
{
	platform_device_unregister(ty1208z_restart_device);
	platform_driver_unregister(&ty1208z_restart_driver);
}
module_exit(ty1208z_ram_restart_exit);
#else
builtin_platform_driver(ty1208z_restart_driver);
#endif
MODULE_LICENSE("GPL");
