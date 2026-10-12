/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAND_PORT_SCAN_H
#define WLAND_PORT_SCAN_H

/* The NETINFO WID contains one RSSI byte, then an 802.11 MAC frame. */
static inline int wland_port_network_frame_length(const u8 *data, size_t length,
						 size_t *frame_length)
{
	u16 message_length, wid_length;

	if (!data || !frame_length)
		return -EINVAL;
	if (length < 8)
		return -EMSGSIZE;
	if (data[0] != 'N' || (MAKE_WORD16(data[4], data[5])) != WID_NETWORK_INFO)
		return -EPROTO;
	message_length = MAKE_WORD16(data[2], data[3]);
	wid_length = MAKE_WORD16(data[6], data[7]);
	if (message_length < 8 || message_length > length ||
	    wid_length < 1 + MAC_HDR_LEN || wid_length > message_length - 8)
		return -EMSGSIZE;
	*frame_length = wid_length - 1;
	return 0;
}

#endif
