/* SPDX-License-Identifier: ISC */
s32 wland_pull_wid(const u8 *buf, u16 buf_len, u16 *WID,
		   const u8 **data, u16 *data_len)
{
	enum wid_type type;
	u16 wid, length, header = 3, trailer = 0;
	u8 checksum = 0;
	unsigned int i, total;

	if (!WID || !data || !data_len)
		return -EINVAL;
	*WID = 0;
	*data = NULL;
	*data_len = 0;
	if (!buf || buf_len < 2)
		return -EMSGSIZE;
	wid = get_le16(buf);
	type = wland_get_wid_type(wid);
	if (type == WID_UNKNOW)
		return -EINVAL;
	/* Standalone query records contain only their WID. */
	if (buf_len == 2) {
		*WID = wid;
		return 2;
	}
	if (type == WID_BIN) {
		if (buf_len < 4)
			return -EMSGSIZE;
		header = 4;
		trailer = 1;
		length = get_le16(buf + 2) & 0x3fff;
	} else {
		length = buf[2];
		if ((type == WID_CHAR && length != 1) ||
		    (type == WID_SHORT && length != 2) ||
		    (type == WID_INT && length != 4))
			return -EINVAL;
	}
	total = header + length + trailer;
	if (total > buf_len)
		return -EMSGSIZE;
	if (type == WID_BIN) {
		for (i = 0; i < length; i++)
			checksum += buf[header + i];
		if (checksum != buf[header + length])
			return -EBADMSG;
	}
	*WID = wid;
	*data = buf + header;
	*data_len = length;
	return total;
}
