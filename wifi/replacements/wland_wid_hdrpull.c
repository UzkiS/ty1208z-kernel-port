/* SPDX-License-Identifier: ISC */
static int wland_wid_hdrpull(struct wland_private *drvr, u8 *val, u16 val_len)
{
	struct wland_proto *prot = drvr->prot;
	const u8 *data;
	u16 wire, packet_len, message_len, wid, data_len, payload_len;
	int used;

	prot->rsplen = 0;
	prot->offset = 0;
	if (drvr->bus_if->state != WLAND_BUS_DATA)
		return -EIO;
	if (val != (u8 *)&prot->msg || val_len < sizeof(prot->msg) ||
	    val_len > sizeof(prot->msg) + sizeof(prot->buf))
		return -EMSGSIZE;

	/* Inspect wire bytes without mutating little-endian header fields. */
	wire = get_le16(val);
	packet_len = wire & CDC_DCMD_LEN_MASK;
	message_len = get_le16(val + 4);
	if ((wire >> CDC_DCMD_LEN_SHIFT) != PKT_TYPE_CFG_RSP ||
	    val[2] != WLAND_WID_MSG_RESP)
		return -EPROTO;
	if (message_len < FMW_HEADER_LEN || packet_len > val_len ||
	    packet_len != message_len + WID_HEADER_LEN)
		return -EMSGSIZE;
	payload_len = packet_len - sizeof(prot->msg);
	used = wland_pull_wid(val + sizeof(prot->msg), payload_len,
			      &wid, &data, &data_len);
	if (used < 0)
		return used;
	if (used <= 2 || used != payload_len)
		return -EPROTO;
	if (wid == WID_STATUS)
		return data_len == 1 && data[0] == STATUS_SUCCESS ? 0 : -EREMOTEIO;
	if (wid != prot->cmd)
		return -EPROTO;
	prot->offset = data - (val + sizeof(prot->msg));
	prot->rsplen = data_len;
	return 0;
}
