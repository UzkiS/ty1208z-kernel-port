/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_SD_RO_POLICY_H
#define HI3798MV100_SD_RO_POLICY_H

#include "hi3798mv100-sd-ident-policy.h"

/* Sector-addressed SDHC/SDXC only. Read at most one 4-KiB page per request.
 * This is the hardware-queue barrier, independent of disk/sysfs read-only
 * flags. Multi-block reads require the exact read STOP sidecar; no CMD23.
 */
static inline int hi3798mv100_sd_ro_request(struct mmc_request *mrq,
					 bool sector_addressed, u64 sectors)
{
	struct mmc_command *cmd = mrq->cmd;
	struct mmc_data *data = mrq->data;
	u32 read_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
	u32 stop_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC;

	if (!hi3798mv100_sd_ident_request(mrq))
		return 0;
	if (!cmd || !sector_addressed || !sectors || sectors > (1ULL << 32) ||
	    mrq->sbc || cmd->data != data)
		return -EPERM;
	/* Error recovery may explicitly stop an interrupted read. */
	if (cmd->opcode == MMC_STOP_TRANSMISSION && !data && !mrq->stop)
		return !cmd->arg && cmd->flags == stop_flags ? 0 : -EPERM;
	if (!data || data->flags != MMC_DATA_READ || data->blksz != 512 ||
	    !data->blocks || data->blocks > 8 || cmd->flags != read_flags ||
	    cmd->arg >= sectors || data->blocks > sectors - cmd->arg)
		return -EPERM;
	if (data->blocks == 1)
		return cmd->opcode == MMC_READ_SINGLE_BLOCK && !mrq->stop &&
		       !data->stop ? 0 : -EPERM;
	if (cmd->opcode != MMC_READ_MULTIPLE_BLOCK || !mrq->stop ||
	    data->stop != mrq->stop || mrq->stop->opcode != MMC_STOP_TRANSMISSION ||
	    mrq->stop->arg || mrq->stop->flags != stop_flags || mrq->stop->data)
		return -EPERM;
	return 0;
}

#endif
