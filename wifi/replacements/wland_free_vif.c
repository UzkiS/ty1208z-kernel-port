/* SPDX-License-Identifier: GPL-2.0-only */
void wland_free_vif(struct wland_cfg80211_info *cfg,
		    struct wland_cfg80211_vif *vif)
{
	/* Failed attach must not leave netdev/ifp pointing at freed storage. */
	if (vif->wdev.netdev && vif->wdev.netdev->ieee80211_ptr == &vif->wdev)
		vif->wdev.netdev->ieee80211_ptr = NULL;
	if (vif->ifp && vif->ifp->vif == vif)
		vif->ifp->vif = NULL;
	list_del(&vif->list);
	cfg->vif_cnt--;
	kfree(vif);
}
