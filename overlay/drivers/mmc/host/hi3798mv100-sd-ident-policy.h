/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_SD_IDENT_POLICY_H
#define HI3798MV100_SD_IDENT_POLICY_H

#include <linux/errno.h>
#include <linux/mmc/core.h>
#include <linux/mmc/mmc.h>
#include <linux/mmc/sd.h>

/* Native SD identification and fixed-size metadata only; no sector access.
 * CMD6 check-mode is a metadata read. SET-mode and ACMD6 bus changes fail.
 */
static inline int hi3798mv100_sd_ident_request(struct mmc_request *mrq)
{
	struct mmc_command *cmd = mrq->cmd;
	struct mmc_data *data = mrq->data;

	if (!cmd || mrq->sbc || mrq->stop || cmd->data != data ||
	    (data && data->stop))
		return -EPERM;
	if (data) {
		if (data->flags != MMC_DATA_READ || data->blocks != 1)
			return -EPERM;
		if (cmd->opcode == SD_APP_SEND_SCR && cmd->arg == 0 &&
		    data->blksz == 8)
			return 0;
		if (cmd->opcode == SD_APP_SD_STATUS && cmd->arg == 0 &&
		    data->blksz == 64)
			return 0;
		/* Actual core queries function group 1 in CHECK mode. */
		if (cmd->opcode == SD_SWITCH && data->blksz == 64 &&
		    cmd->arg == 0x00fffff0)
			return 0;
		return -EPERM;
	}

	switch (cmd->opcode) {
	case MMC_GO_IDLE_STATE:
	case MMC_ALL_SEND_CID:
	case SD_SEND_RELATIVE_ADDR:
		return cmd->arg == 0 ? 0 : -EPERM;
	case SD_SEND_IF_COND:
		return cmd->arg == 0x1aa ? 0 : -EPERM;
	case SD_APP_OP_COND:
		/* Host never advertises S18R/XPC/SD Express or low-voltage OCR. */
		return cmd->arg & ~0x40ff8000U ? -EPERM : 0;
	case MMC_APP_CMD:
	case MMC_SELECT_CARD:
		return (cmd->arg & 0xffffU) == 0 ? 0 : -EPERM;
	case MMC_SEND_CSD:
	case MMC_SEND_CID:
	case MMC_SEND_STATUS:
		return cmd->arg && (cmd->arg & 0xffffU) == 0 ? 0 : -EPERM;
	default:
		return -EPERM;
	}
}

#endif
