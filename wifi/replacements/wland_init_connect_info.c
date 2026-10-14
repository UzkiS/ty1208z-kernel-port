/* SPDX-License-Identifier: GPL-2.0-only */
static s32 wland_init_connect_info(struct wland_cfg80211_info *cfg)
{
	struct wland_cfg80211_vif *vif;
	struct wland_cfg80211_connect_info *conn_info;
	int i;

	list_for_each_entry(vif, &cfg->vif_list, list) {
		conn_info = &vif->conn_info;
		atomic_set(&conn_info->tid_map, 0);
		for (i = 0; i < 8; i++) {
			conn_info->tid_jiffies[i] = jiffies;
			conn_info->tid_num[i] = 0;
		}
		conn_info->ndev = cfg_to_ndev(cfg);
		conn_info->data = cfg;
		timer_setup(&conn_info->timer, wland_connect_timer, 0);
		timer_setup(&conn_info->connect_restorework_timeout,
			    wland_connect_restorework_timeout, 0);
		conn_info->timer_on = false;
		INIT_WORK(&conn_info->work, wland_cfg80211_connect_worker);
		INIT_WORK(&conn_info->connect_restorework_timeout_work,
			  wland_cfg80211_connect_restorework_timeout_worker);
		spin_lock_init(&conn_info->sta_info_lock);
		INIT_LIST_HEAD(&conn_info->sta_info_list);
#ifdef WLAND_AMSDU_TX
		wland_amsdu_tx_init(vif->ifp);
#endif
		/* Cleanup is now safe even if allocation of this queue fails. */
		conn_info->initialized = true;
		conn_info->connect_wq = create_singlethread_workqueue("connect_wq");
		if (!conn_info->connect_wq)
			return -ENOMEM;
	}
	return 0;
}
