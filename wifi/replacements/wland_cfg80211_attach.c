/* SPDX-License-Identifier: GPL-2.0-only */
struct wland_cfg80211_info *wland_cfg80211_attach(struct wland_private *drvr,
						struct device *busdev)
{
	struct net_device *ndev;
	struct device *ndev_parent;
	struct wland_cfg80211_info *cfg;
	struct wiphy *wiphy;
	struct wland_cfg80211_vif *vif, *tmp;
	struct wland_if *ifp;
#ifdef WLAND_P2P_SUPPORT
	bool p2p_attached = false;
#endif
	s32 err;

	if (!drvr->iflist[0] || !drvr->iflist[0]->ndev)
		return NULL;
	ndev = drvr->iflist[0]->ndev;
	ndev_parent = ndev->dev.parent;
	ifp = netdev_priv(ndev);
	wiphy = wland_setup_wiphy(busdev);
	if (IS_ERR(wiphy))
		return NULL;

	cfg = wiphy_priv(wiphy);
	cfg->wiphy = wiphy;
	cfg->pub = drvr;
	init_waitqueue_head(&cfg->vif_event.vif_wq);
	init_waitqueue_head(&cfg->scanid_wait);
	mutex_init(&cfg->vif_event.vif_event_lock);
	mutex_init(&cfg->usr_sync);
	mutex_init(&cfg->scan_result_lock);
	INIT_LIST_HEAD(&cfg->vif_list);
	INIT_LIST_HEAD(&cfg->scan_result_list);
	cfg->scan_results.version = SCAN_VERSION_NUM;
	cfg->scan_results.count = 0;
	cfg->scan_info.ifp = ifp;
	cfg->scan_info.escan_state = SCAN_STATE_IDLE;
	timer_setup(&cfg->scan_timeout, wland_scan_timeout, 0);
	INIT_WORK(&cfg->scan_report_work, wland_cfg80211_scan_report_worker);
	init_completion(&cfg->vif_disabled);
	init_completion(&cfg->disconnecting_wait);
	cfg->in_disconnecting = false;
	cfg->in_waiting = false;
	cfg->scan_request = NULL;
	memset(&cfg->escan_info, 0, sizeof(cfg->escan_info));
	cfg->pwr_save = true;
	cfg->roam_on = false;
	cfg->active_scan = true;
	cfg->dongle_up = false;

	vif = wland_alloc_vif(cfg, NL80211_IFTYPE_STATION, false);
	if (IS_ERR(vif)) {
		err = PTR_ERR(vif);
		goto fail;
	}
	vif->ifp = ifp;
	vif->wdev.netdev = ndev;
	vif->profile.mode = WLAND_ERR_MODE;
	ifp->vif = vif;
	ndev->ieee80211_ptr = &vif->wdev;
	SET_NETDEV_DEV(ndev, wiphy_dev(wiphy));

	err = wland_init_priv_mem(cfg);
	if (err)
		goto fail;
#ifdef WLAND_P2P_SUPPORT
	err = cfg80211_p2p_attach(cfg);
	if (err)
		goto fail;
	p2p_attached = true;
#else
	cfg->p2p.bss_idx[P2PAPI_BSSCFG_PRIMARY].vif = vif;
#endif
	err = wland_init_connect_info(cfg);
	if (err)
		goto fail;
#ifdef WLAND_BTCOEX_SUPPORT
	err = wland_btcoex_attach(cfg);
	if (err)
		goto fail;
#endif
	cfg->d11inf.io_type = WLAND_D11N_IOTYPE;
	wland_d11_attach(&cfg->d11inf);
#ifdef WLAND_MONITOR_SUPPORT
	wland_monitor_init(drvr);
#endif
	/* Publish callbacks only after all their objects are initialized. */
	wland_register_event_handlers(cfg);
	return cfg;

fail:
	WLAND_ERR("cfg80211 attach failed (%d)\n", err);
	timer_shutdown_sync(&cfg->scan_timeout);
	cancel_work_sync(&cfg->scan_report_work);
	wland_deinit_connect_info(cfg);
#ifdef WLAND_P2P_SUPPORT
	if (p2p_attached)
		cfg80211_p2p_detach(&cfg->p2p);
#endif
	wland_deinit_priv_mem(cfg);
	list_for_each_entry_safe(vif, tmp, &cfg->vif_list, list)
		wland_free_vif(cfg, vif);
	SET_NETDEV_DEV(ndev, ndev_parent);
	wiphy_unregister(wiphy);
	wiphy_free(wiphy);
	return NULL;
}
