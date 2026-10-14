// SPDX-License-Identifier: GPL-2.0-only
static s32 wland_get_assoc_ies(struct wland_cfg80211_info *cfg,
	struct wland_if *ifp)
{
	struct wland_cfg80211_connect_info *info = &ifp->vif->conn_info;
	u8 *request = NULL, *response = NULL;
	u16 request_len, response_len;
	int ret;

	/* Report the IEs actually sent by firmware, not supplicant's proposal. */
	ret = wland_fil_get_cmd_data(ifp, WID_ASSOC_REQ_INFO, cfg->extra_buf,
				     WLAND_ASSOC_INFO_MAX);
	if (ret < 0)
		return ret;
	/* These WIDs return 802.11 frame bodies. The WID decoder already
	 * removes the wire length; the first byte here is Capability, not length.
	 * Association requests have Capability + Listen Interval (4 bytes).
	 */
	if (ret < 4)
		return -EBADMSG;
	request_len = ret - 4;
	if (request_len) {
		request = kmemdup(cfg->extra_buf + 4, request_len, GFP_KERNEL);
		if (!request)
			return -ENOMEM;
	}

	ret = wland_fil_get_cmd_data(ifp, WID_ASSOC_RES_INFO, cfg->extra_buf,
				     WLAND_ASSOC_INFO_MAX);
	if (ret < 0)
		goto failed;
	/* Responses have Capability + Status + AID (6 bytes). */
	if (ret < 6) {
		ret = -EBADMSG;
		goto failed;
	}
	response_len = ret - 6;
	if (response_len) {
		response = kmemdup(cfg->extra_buf + 6, response_len, GFP_KERNEL);
		if (!response) {
			ret = -ENOMEM;
			goto failed;
		}
	}

	kfree(info->req_ie);
	kfree(info->resp_ie);
	info->req_ie = request;
	info->req_ie_len = request_len;
	info->resp_ie = response;
	info->resp_ie_len = response_len;
	WLAND_DBG(CFG80211, INFO, "Firmware association IEs: request %u response %u\n",
		  request_len, response_len);
	return 0;

failed:
	kfree(request);
	return ret;
}
