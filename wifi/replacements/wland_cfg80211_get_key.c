// SPDX-License-Identifier: GPL-2.0-only
static s32 wland_cfg80211_get_key(struct wiphy *wiphy, struct net_device *ndev,
	int link_id, u8 key_idx, bool pairwise, const u8 *mac_addr, void *cookie,
	void (*callback)(void *cookie, struct key_params *params))
{
	struct wland_if *ifp = netdev_priv(ndev);

	if (link_id > 0)
		return -EOPNOTSUPP;
	if (key_idx >= DOT11_MAX_DEFAULT_KEYS || !callback)
		return -EINVAL;
	if (!wland_check_vif_up(ifp->vif))
		return -EIO;

	/* Do not deliver empty or guessed key material to cfg80211. */
	return -EOPNOTSUPP;
}
