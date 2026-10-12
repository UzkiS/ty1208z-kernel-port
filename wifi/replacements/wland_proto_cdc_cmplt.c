/* SPDX-License-Identifier: ISC */
static int wland_proto_cdc_cmplt(struct wland_private *drvr, u8 id, u16 len)
{
	struct wland_proto *prot = drvr->prot;
	int attempt, ret;

	if (len < sizeof(prot->msg) ||
	    len > sizeof(prot->msg) + sizeof(prot->buf))
		return -EMSGSIZE;
	for (attempt = 0; attempt < RETRIES; attempt++) {
		ret = wland_bus_rxctl(drvr->bus_if, (u8 *)&prot->msg, len);
		if (ret < 0)
			return ret;
		/* Do not compare the stale request ID after a short bus response. */
		if (ret < sizeof(prot->msg) || ret > len)
			return -EMSGSIZE;
		if (prot->msg.wid_msg_id == id)
			return ret;
	}
	return -EPROTO;
}
