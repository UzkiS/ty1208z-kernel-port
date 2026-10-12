/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAND_PORT_KEY_VALIDATE_H
#define WLAND_PORT_KEY_VALIDATE_H

/* Only ordinary data keys fit the legacy PTK/GTK command formats. */
static inline int wland_port_validate_key(const struct key_params *params,
					 u8 key_idx)
{
	int length;

	if (!params || !params->key || key_idx >= DOT11_MAX_DEFAULT_KEYS ||
	    params->seq_len < 0 || params->seq_len > 8 ||
	    (params->seq_len && !params->seq))
		return -EINVAL;

	switch (params->cipher) {
	case WLAN_CIPHER_SUITE_WEP40:
		length = 5;
		break;
	case WLAN_CIPHER_SUITE_WEP104:
		length = 13;
		break;
	case WLAN_CIPHER_SUITE_TKIP:
		length = 32;
		break;
	case WLAN_CIPHER_SUITE_CCMP:
		length = 16;
		break;
	default:
		/* BIP/WAPI require their own proven firmware command, not GTK. */
		return -EOPNOTSUPP;
	}

	return params->key_len == length ? 0 : -EINVAL;
}

static inline bool wland_port_key_role(enum nl80211_iftype type)
{
	return type == NL80211_IFTYPE_STATION || type == NL80211_IFTYPE_AP ||
	       type == NL80211_IFTYPE_P2P_CLIENT || type == NL80211_IFTYPE_P2P_GO;
}

#endif
