// SPDX-License-Identifier: GPL-2.0-only
static s32 wland_cfg80211_del_key(struct wiphy *wiphy, struct net_device *ndev,
	int link_id, u8 key_idx, bool pairwise, const u8 *mac_addr)
{
	struct wland_if *ifp = netdev_priv(ndev);

	if (link_id > 0)
		return -EOPNOTSUPP;
	if (key_idx >= DOT11_MAX_DEFAULT_KEYS)
		return -EINVAL;
	if (!wland_check_vif_up(ifp->vif))
		return -EIO;

	/* The pinned source has no implemented key-removal request. */
	return -EOPNOTSUPP;
}
