/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef WLAND_PORT_USB_H
#define WLAND_PORT_USB_H

/* Keep the firmware's USB transfer rounding, but allocate and zero every
 * transmitted byte. Preserve skb ownership and its logical frame length.
 */
static inline int wland_port_usb_tx_length(struct sk_buff *skb)
{
	unsigned int length = skb->len;
	unsigned int remainder = length % 512;
	int err;

	if (!length || length > CDC_DCMD_LEN_MASK)
		return -EMSGSIZE;
	if (length <= 1536 && (!remainder || remainder > 64))
		length += (remainder ? 512 - remainder : 0) + 4;
	if (length > skb->len) {
		err = __skb_pad(skb, length - skb->len, false);
		if (err)
			return err;
	}
	return length;
}

#endif
