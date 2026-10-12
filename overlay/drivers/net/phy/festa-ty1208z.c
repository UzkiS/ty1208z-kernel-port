// SPDX-License-Identifier: GPL-2.0-only
/* Inherited-state experiment. No PHY firmware/reset/expanded-register writes. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/phy.h>

static int ty1208z_festa_probe(struct phy_device *phy)
{
	int high, low;

	if ((!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic") &&
	     !of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-net")) ||
	    phy->mdio.addr != 1 || phy->phy_id != 0x20669823)
		return -ENODEV;
	high = phy_read(phy, MII_PHYSID1);
	if (high < 0)
		return high;
	low = phy_read(phy, MII_PHYSID2);
	if (low < 0)
		return low;
	if (((u32)high << 16 | low) != 0x20669823)
		return -ENODEV;
	phydev_info(phy, "ETH_NET_PHY_VERIFIED id=20669823 inherited-no-reset\n");
	return 0;
}

static struct phy_driver ty1208z_festa_driver[] = {
	{
		.phy_id = 0x20669823,
		.phy_id_mask = 0xffffffff,
		.name = "TY1208Z FESTAv220 inherited",
		.probe = ty1208z_festa_probe,
		.get_features = genphy_read_abilities,
		.config_aneg = genphy_config_aneg,
		.read_status = genphy_read_status,
		/* Deliberately no soft_reset, suspend/resume or vendor fixup. */
	},
};
module_phy_driver(ty1208z_festa_driver);
MODULE_LICENSE("GPL");

static const struct mdio_device_id ty1208z_festa_ids[] = {
	{ 0x20669823, 0xffffffff },
	{ }
};
MODULE_DEVICE_TABLE(mdio, ty1208z_festa_ids);
