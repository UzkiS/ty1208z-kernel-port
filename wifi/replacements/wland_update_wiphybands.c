/* SPDX-License-Identifier: ISC */
static s32 wland_update_wiphybands(struct wland_cfg80211_info *cfg, bool notify)
{
	struct wland_if *ifp = netdev_priv(cfg_to_ndev(cfg));
	struct wiphy *wiphy = cfg_to_wiphy(cfg);
	struct ieee80211_sta_ht_cap ht = {};
	u8 nmode = 0, short_gi = 0;
	s32 err;

	/* The immutable regulatory domain was applied before wiphy_register.
	 * ndo_open already holds RTNL, so reapplying it here would deadlock on
	 * modern cfg80211's rtnl_lock(). Updating HT capabilities needs no hint.
	 */
	(void)notify;

	/* These are existing RDA byte WIDs, not Broadcom named iovars. */
	err = wland_fil_get_cmd_data(ifp, WID_11N_ENABLE, &nmode, sizeof(nmode));
	if (err < 0)
		return err;
	if (err != sizeof(nmode) || nmode > 1)
		return -EPROTO;
	if (nmode) {
		err = wland_fil_get_cmd_data(ifp, WID_11N_SHORT_GI_ENABLE,
					     &short_gi, sizeof(short_gi));
		if (err < 0)
			return err;
		if (err != sizeof(short_gi) || short_gi > 1)
			return -EPROTO;

		/* The vendor's 5995 profile is 2.4-GHz, one-stream HT20/HT40.
		 * Channel/rate tables are static hardware declarations. Only the
		 * acknowledged N/short-GI operating state is read from firmware.
		 */
		ht.ht_supported = true;
		ht.cap = IEEE80211_HT_CAP_SUP_WIDTH_20_40;
		if (short_gi)
			ht.cap |= IEEE80211_HT_CAP_SGI_20 | IEEE80211_HT_CAP_SGI_40;
		ht.ampdu_factor = IEEE80211_HT_MAX_AMPDU_64K;
		ht.ampdu_density = IEEE80211_HT_MPDU_DENSITY_16;
		ht.mcs.rx_mask[0] = 0xff;
	}

	/* Failed replies leave the previously published band unchanged. */
	__wl_band_2ghz.ht_cap = ht;
	wiphy->bands[NL80211_BAND_2GHZ] = &__wl_band_2ghz;
	return 0;
}
