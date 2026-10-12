/* SPDX-License-Identifier: GPL-2.0-only */
static int wland_parse_network_info(struct wland_bss_info_le *bi,
				   const u8 *data, size_t length)
{
	struct wland_bss_info_le parsed = {};
	const size_t fixed_length = MAC_HDR_LEN + TIME_STAMP_LEN +
		BEACON_INTERVAL_LEN + CAP_INFO_LEN;
	const u8 *frame, *ies, *rates[2] = {};
	size_t frame_length, ie_length, offset, rate_lengths[2] = {};
	bool have_ssid = false;
	int err, index;

	if (!bi)
		return -EINVAL;
	err = wland_port_network_frame_length(data, length, &frame_length);
	if (err)
		return err;
	if (frame_length < fixed_length)
		return -EMSGSIZE;
	frame = data + 9;
	if ((frame[0] & 0xfc) != BEACON && (frame[0] & 0xfc) != PROBE_RSP)
		return -EPROTO;
	if (frame[1] & 0x03)
		return -EPROTO;
	ies = frame + fixed_length;
	ie_length = frame_length - fixed_length;

	/* Validate every IE before allocating or publishing a BSS. */
	for (offset = 0; offset < ie_length; ) {
		const u8 *element = ies + offset, *value;
		size_t element_length;

		if (ie_length - offset < 2)
			return -EMSGSIZE;
		element_length = element[1];
		if (element_length > ie_length - offset - 2)
			return -EMSGSIZE;
		value = element + 2;
		switch (element[0]) {
		case WLAN_EID_SSID:
			if (have_ssid || element_length > sizeof(parsed.SSID))
				return -EPROTO;
			have_ssid = true;
			parsed.SSID_len = element_length;
			memcpy(parsed.SSID, value, element_length);
			break;
		case WLAN_EID_SUPP_RATES:
		case WLAN_EID_EXT_SUPP_RATES:
			index = element[0] == WLAN_EID_EXT_SUPP_RATES;
			if (!rates[index]) {
				rates[index] = value;
				rate_lengths[index] = element_length;
			}
			break;
		case WLAN_EID_DS_PARAMS:
			if (element_length != 1)
				return -EPROTO;
			parsed.ctl_ch = value[0];
			break;
		case WLAN_EID_TIM:
			if (element_length < 4)
				return -EPROTO;
			parsed.dtim_period = value[1];
			break;
		case WLAN_EID_HT_CAPABILITY:
			if (element_length != sizeof(struct ieee80211_ht_cap))
				return -EPROTO;
			parsed.n_enable = true;
			break;
		case WLAN_EID_VENDOR_SPECIFIC:
			if (element_length >= TLV_OUI_LEN + 1 &&
			    !memcmp(value, WPA_OUI, TLV_OUI_LEN) &&
			    value[TLV_OUI_LEN] == WME_OUI_TYPE)
				parsed.wmm_enable = true;
			break;
		}
		offset += element_length + 2;
	}

	/* Append extended rates contiguously and within the declared rate limit. */
	for (index = 0; index < 2; index++) {
		size_t limit = min_t(size_t, MAX_RATES, sizeof(parsed.rateset.rates));
		size_t count = min_t(size_t, rate_lengths[index],
				     limit - parsed.rateset.count);

		if (count)
			memcpy(parsed.rateset.rates + parsed.rateset.count,
			       rates[index], count);
		parsed.rateset.count += count;
	}
#ifdef WLAND_RSSIOFFSET_SUPPORT
	parsed.RSSI = (s8)(data[8] < WLAND_RSSI_MAXVAL_FOR_OFFSET ?
			  data[8] + WLAND_RSSI_OFFSET : data[8]);
#else
	parsed.RSSI = (s8)data[8];
#endif
	memcpy(parsed.BSSID, frame + 16, ETH_ALEN);
	parsed.beacon_period = MAKE_WORD16(frame[MAC_HDR_LEN + TIME_STAMP_LEN],
					 frame[MAC_HDR_LEN + TIME_STAMP_LEN + 1]);
	parsed.capability = MAKE_WORD16(frame[fixed_length - 2],
				      frame[fixed_length - 1]);
	parsed.ie_length = ie_length;
	parsed.length = sizeof(parsed);
	if (ie_length) {
		parsed.ie = kmemdup(ies, ie_length, GFP_KERNEL);
		if (!parsed.ie)
			return -ENOMEM;
	}
	*bi = parsed;
	WLAND_DBG(CFG80211, TRACE, "SSID=%.*s ie_length=%u length=%u\n",
		  (int)bi->SSID_len, bi->SSID, bi->ie_length, bi->length);
	return 0;
}
