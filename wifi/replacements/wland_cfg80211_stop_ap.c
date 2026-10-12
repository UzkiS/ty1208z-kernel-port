// SPDX-License-Identifier: GPL-2.0-only
static int wland_cfg80211_stop_ap(struct wiphy *wiphy, struct net_device *ndev,
	unsigned int link_id)
{
	struct wland_if *ifp = netdev_priv(ndev);
	enum nl80211_iftype role = ifp->vif->wdev.iftype;
	s32 err;

	if (link_id)
		return -EOPNOTSUPP;
	if (role != NL80211_IFTYPE_AP && role != NL80211_IFTYPE_P2P_GO)
		return -EOPNOTSUPP;
	if (ndev->ieee80211_ptr->iftype != role)
		return -EINVAL;
	if (!wland_check_vif_up(ifp->vif))
		return -EIO;
	/* Only this interface has a stop command in the pinned implementation. */
	if (ifp->bssidx != P2PAPI_BSSCFG_DEVICE)
		return -EOPNOTSUPP;
	if (!is_valid_ether_addr(ifp->mac_addr))
		return -EINVAL;

	err = wland_fil_set_cmd_data(ifp, WID_STOP_AP_MAC1,
				     ifp->mac_addr, ETH_ALEN);
	if (err < 0)
		return err;

	/* Keep the configured AP role, but publish stopped state after the reply. */
	set_bit(VIF_STATUS_AP_CREATING, &ifp->vif->sme_state);
	clear_bit(VIF_STATUS_AP_CREATED, &ifp->vif->sme_state);
	return 0;
}
