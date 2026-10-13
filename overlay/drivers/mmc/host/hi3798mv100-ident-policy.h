/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_IDENT_POLICY_H
#define HI3798MV100_IDENT_POLICY_H

#include <linux/errno.h>
#include <linux/mmc/core.h>
#include <linux/mmc/mmc.h>
#include <linux/mmc/ty1208z-samples.h>

/* Identification plus optional fixed read samples. No settings or data writes. */
static inline int hi3798mv100_ident_request(struct mmc_request *mrq)
{
	struct mmc_command *cmd;
	struct mmc_data *data;

	if (!mrq)
		return -EPERM;
	cmd = mrq->cmd;
	data = mrq->data;

	if (!cmd || mrq->sbc || mrq->stop)
		return -EPERM;
	if (cmd->data != data || (data && data->stop))
		return -EPERM;
	if (data) {
		if (data->flags != MMC_DATA_READ || data->blocks != 1 ||
		    data->blksz != 512)
			return -EPERM;
		if (cmd->opcode == MMC_SEND_EXT_CSD && cmd->arg == 0)
			return 0;
#ifdef CONFIG_HI3798MV100_EMMC_READ_SAMPLES
		if (cmd->opcode == MMC_READ_SINGLE_BLOCK && ty1208z_sample_sector(cmd->arg))
			return 0;
#endif
		return -EPERM;
	}

	/* Core treats -EBADMSG as an unsupported optional card setting. */
	if (cmd->opcode == MMC_SWITCH)
		return -EBADMSG;

	switch (cmd->opcode) {
	case MMC_GO_IDLE_STATE:
	case MMC_ALL_SEND_CID:
		return cmd->arg == 0 ? 0 : -EPERM;
	case MMC_SEND_OP_COND:
		/* Core repeats a busy OCR query using the card's advertised OCR.
		 * Dual-voltage eMMC includes bit 7, even with the host kept at 3.3 V.
		 * This is CMD1 negotiation, not an I/O-voltage switch or card setting.
		 */
		return cmd->arg & ~0x40ff8080U ? -EPERM : 0;
	case MMC_SET_RELATIVE_ADDR:
	case MMC_SEND_CSD:
	case MMC_SEND_CID:
	case MMC_SEND_STATUS:
		return cmd->arg == 0x00010000 ? 0 : -EPERM;
	case MMC_SELECT_CARD:
		return cmd->arg == 0 || cmd->arg == 0x00010000 ? 0 : -EPERM;
	default:
		return -EPERM;
	}
}

#endif
