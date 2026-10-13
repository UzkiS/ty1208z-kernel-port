/* SPDX-License-Identifier: ISC */
s32 wland_get_assoc_ies_from_frame(struct wland_if *ifp,
				 u8 *frame, u16 frame_len, u8 frame_stype)
{
	struct wland_cfg80211_connect_info *conn_info;
	struct wland_sta_info *sta_info = NULL, *entry;
	const u8 *ies, *mac_addr;
	u8 *copy = NULL, *previous;
	size_t header, fixed, ie_length, offset;
	bool wmm = false, ht = false;
	int i;

	if (!ifp || !ifp->vif || !frame)
		return -EINVAL;
	if (frame_len < MAC_HDR_LEN)
		return -EMSGSIZE;
	if ((frame[0] & 0x03) || (frame[0] & 0xfc) != frame_stype ||
	    (frame[1] & 0x03))
		return -EPROTO;
	if (frame_stype == ASSOC_REQ)
		fixed = CAP_INFO_LEN + LISTEN_INTERVAL_LEN;
	else if (frame_stype == ASSOC_RSP)
		fixed = CAP_INFO_LEN + STATUS_CODE_LEN + AID_LEN;
	else
		return -EOPNOTSUPP;
	header = GET_MGMT_HDR_LEN(frame);
	if (header > frame_len || fixed > frame_len - header)
		return -EMSGSIZE;
	ies = frame + header + fixed;
	ie_length = frame_len - header - fixed;
	mac_addr = frame + MAC_HDR_ADDR2_OFFSET;

	/* Validate the complete IE stream before allocation or state changes. */
	for (offset = 0; offset < ie_length; ) {
		const u8 *element = ies + offset;
		size_t length;

		if (ie_length - offset < 2)
			return -EMSGSIZE;
		length = element[1];
		if (length > ie_length - offset - 2)
			return -EMSGSIZE;
		if ((element[0] == WLAN_EID_SSID && length > 32) ||
		    (element[0] == WLAN_EID_HT_CAPABILITY &&
		     length != sizeof(struct ieee80211_ht_cap)))
			return -EPROTO;
		offset += length + 2;
	}
	if (ie_length) {
		copy = kmemdup(ies, ie_length, GFP_ATOMIC);
		if (!copy)
			return -ENOMEM;
		wmm = !!wland_find_wmmie(copy, ie_length);
		ht = !!wland_parse_tlvs(copy, ie_length, WLAN_EID_HT_CAPABILITY);
	}
	conn_info = &ifp->vif->conn_info;
	if (frame_stype == ASSOC_RSP) {
		previous = conn_info->resp_ie;
		conn_info->resp_ie = copy;
		conn_info->resp_ie_len = ie_length;
		kfree(previous);
		return 0;
	}

	spin_lock_bh(&conn_info->sta_info_lock);
	list_for_each_entry(entry, &conn_info->sta_info_list, list) {
		if (!memcmp(mac_addr, entry->mac_addr, ETH_ALEN)) {
			sta_info = entry;
			break;
		}
	}
	if (!sta_info) {
		sta_info = kzalloc(sizeof(*sta_info), GFP_ATOMIC);
		if (!sta_info) {
			spin_unlock_bh(&conn_info->sta_info_lock);
			kfree(copy);
			return -ENOMEM;
		}
		atomic_set(&sta_info->tid_map, 0);
		for (i = 0; i < 8; i++) {
			sta_info->tid_jiffies[i] = jiffies;
			sta_info->tid_num[i] = 0;
		}
		memcpy(sta_info->mac_addr, mac_addr, ETH_ALEN);
		list_add_tail(&sta_info->list, &conn_info->sta_info_list);
	}
	previous = sta_info->assoc_req_ie;
	sta_info->assoc_req_ie = copy;
	sta_info->assoc_req_ie_len = ie_length;
	sta_info->wmm_enable = wmm;
	sta_info->n_enable = ht;
	sta_info->connect = 0;
	sta_info->aid = 0;
	spin_unlock_bh(&conn_info->sta_info_lock);
	kfree(previous);
	return 0;
}
