// SPDX-License-Identifier: GPL-2.0-only
static s32 wland_cfg80211_change_virtual_iface(struct wiphy *wiphy,
	struct net_device *ndev, enum nl80211_iftype type,
	struct vif_params *params)
{
	struct wland_if *ifp = netdev_priv(ndev);
	struct wland_cfg80211_vif *vif = ifp->vif;

	/* USB unregister needs RTNL, which the cfg80211 caller already holds.
	 * Never wait here for the vendor repower worker. The netifd RDA backend
	 * unloads/reloads the module outside this callback to select firmware.
	 */
	if (ifp->bssidx)
		return -EOPNOTSUPP;
	switch (type) {
	case NL80211_IFTYPE_STATION:
		if (strcmp(rdawlan_firmware_path, "sta"))
			return -EOPNOTSUPP;
		vif->mode = WL_MODE_BSS;
		break;
	case NL80211_IFTYPE_AP:
		if (strcmp(rdawlan_firmware_path, "ap"))
			return -EOPNOTSUPP;
		vif->mode = WL_MODE_AP;
		break;
	default:
		return -EOPNOTSUPP;
	}
	vif->wdev.iftype = type;
	return 0;
}
