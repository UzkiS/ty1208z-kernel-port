/* SPDX-License-Identifier: ISC */
#ifndef RDA_USB_IDENTITY_PROTOCOL_H
#define RDA_USB_IDENTITY_PROTOCOL_H

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Pinned wland_wid.h/c: only these three query records are permitted. */
#define RDA_ID_STATE 0x201e
#define RDA_ID_REVISION 0x0416
#define RDA_ID_FIRMWARE 0x3001

static uint16_t rda_id_le16(const uint8_t *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static int rda_id_query(uint16_t wid, uint8_t seq, uint8_t out[8])
{
    if (wid != RDA_ID_STATE && wid != RDA_ID_REVISION && wid != RDA_ID_FIRMWARE)
        return -EPERM;
    if (!out)
        return -EINVAL;
    const uint8_t query[8] = {8, 0x40, 'Q', seq, 6, 0, (uint8_t)wid, wid >> 8};
    memcpy(out, query, sizeof(query));
    return 8;
}

/* Match both protocol lengths, type, ID, WID and exact typed data size. */
static int rda_id_response(const uint8_t *in, size_t length, uint16_t wid,
                           uint8_t seq, uint8_t out[20])
{
    if (!in || length < 9 || length > 512)
        return -EMSGSIZE;
    if (!out)
        return -EINVAL;
    if (wid != RDA_ID_STATE && wid != RDA_ID_REVISION && wid != RDA_ID_FIRMWARE)
        return -EPERM;
    uint16_t wire = rda_id_le16(in);
    size_t packet = wire & 0x0fff;
    if (wire >> 12 != 3 || in[2] != 'R')
        return -EPROTO;
    if (packet < 9 || packet > length || rda_id_le16(in + 4) != packet - 2)
        return -EMSGSIZE;
    for (size_t i = packet; i < length; i++)
        if (in[i])
            return -EPROTO;
    if (in[3] != seq)
        return -EAGAIN;
    uint16_t reply = rda_id_le16(in + 6);
    size_t size = in[8];
    if (packet != 9 + size)
        return -EMSGSIZE;
    if (reply == 5) /* WID_STATUS is an acknowledgement, not identity data. */
        return size == 1 && in[9] == 1 ? -ENODATA : -EREMOTEIO;
    if (reply != wid)
        return -EPROTO;
    if ((wid == RDA_ID_STATE && size != 4) ||
        (wid == RDA_ID_REVISION && size != 1) ||
        (wid == RDA_ID_FIRMWARE && (size == 0 || size > 20)))
        return -EMSGSIZE;
    memcpy(out, in + 9, size);
    return (int)size;
}

/* Exact 71-byte descriptor stream measured on this board, including all five
 * endpoints. The pinned driver uses the first bulk OUT/IN endpoints (01/82)
 * for WID messages, not the additional 64-byte 03/83 pair. */
static int rda_id_descriptors(const uint8_t *in, size_t length)
{
    static const uint8_t expected[] = {
        18, 1, 0, 2, 0, 0, 0, 64, 4, 30, 136, 136, 0, 0, 1, 2, 0, 1,
        9, 2, 53, 0, 1, 1, 0, 160, 250, 9, 4, 0, 0, 5, 255, 255, 255, 0,
        7, 5, 1, 2, 0, 2, 0, 7, 5, 130, 2, 0, 2, 0,
        7, 5, 3, 2, 64, 0, 0, 7, 5, 131, 2, 64, 0, 0,
        7, 5, 132, 2, 0, 2, 0
    };
    return in && length == sizeof(expected) && !memcmp(in, expected, sizeof(expected))
           ? 0 : -ENODEV;
}

#endif
