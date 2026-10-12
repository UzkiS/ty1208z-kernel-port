/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAND_PORT_KEY_H
#define WLAND_PORT_KEY_H

/* Caller provides a 32-byte firmware key buffer; never read padding from key. */
static inline int wland_port_copy_key(u8 *out, const u8 *key, int length,
				     bool swap_mic)
{
	if (!key || (length != 5 && length != 13 && length != 16 && length != 32))
		return -EINVAL;
	memset(out, 0, 32);
	memcpy(out, key, length);
	if (length == 32 && swap_mic) {
		memcpy(out + 16, key + 24, 8);
		memcpy(out + 24, key + 16, 8);
	}
	return 0;
}

#endif
