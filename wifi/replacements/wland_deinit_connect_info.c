/* SPDX-License-Identifier: GPL-2.0-only */
static s32 wland_deinit_connect_info(struct wland_cfg80211_info *cfg)
{
	struct wland_cfg80211_vif *vif;
	struct wland_cfg80211_connect_info *conn_info;
	struct wland_sta_info *sta_info, *sta_info_tmp;

	list_for_each_entry(vif, &cfg->vif_list, list) {
		conn_info = &vif->conn_info;
		if (!conn_info->initialized)
			continue;

		/* Stop timer producers before draining either consumer. Shutdown
		 * prevents a running work item from rearming a timer during teardown.
		 */
		timer_shutdown_sync(&conn_info->timer);
		timer_shutdown_sync(&conn_info->connect_restorework_timeout);
		conn_info->timer_on = false;
		cancel_work_sync(&conn_info->work);
		cancel_work_sync(&conn_info->connect_restorework_timeout_work);
		if (conn_info->connect_wq) {
			destroy_workqueue(conn_info->connect_wq);
			conn_info->connect_wq = NULL;
		}

		spin_lock_bh(&conn_info->sta_info_lock);
		list_for_each_entry_safe(sta_info, sta_info_tmp,
					 &conn_info->sta_info_list, list) {
			list_del(&sta_info->list);
			kfree(sta_info->assoc_req_ie);
			kfree(sta_info);
		}
		spin_unlock_bh(&conn_info->sta_info_lock);
#ifdef WLAND_AMSDU_TX
		wland_amsdu_tx_deinit(vif->ifp);
#endif
		kfree(conn_info->req_ie);
		conn_info->req_ie = NULL;
		conn_info->req_ie_len = 0;
		kfree(conn_info->resp_ie);
		conn_info->resp_ie = NULL;
		conn_info->resp_ie_len = 0;
		conn_info->initialized = false;
	}
	return 0;
}
