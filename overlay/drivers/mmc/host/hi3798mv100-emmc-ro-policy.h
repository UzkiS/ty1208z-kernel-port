/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_EMMC_RO_POLICY_H
#define HI3798MV100_EMMC_RO_POLICY_H

#include "hi3798mv100-ident-policy.h"

/* Only the measured, sector-addressed user area. No CMD23, partition switch,
 * boot/RPMB access, settings, writes or erase. Queue protection remains even
 * if a userspace disk read-only flag is cleared.
 */
static inline int hi3798mv100_emmc_ro_request(struct mmc_request *mrq,
					   bool user_area, u64 sectors)
{
	struct mmc_command *cmd;
	struct mmc_data *data;
	u32 read_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
	u32 stop_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC;
	int metadata;

	if (!mrq)
		return -EPERM;
	cmd = mrq->cmd;
	data = mrq->data;
	metadata = hi3798mv100_ident_request(mrq);
	if (cmd && cmd->opcode != MMC_READ_SINGLE_BLOCK &&
	    cmd->opcode != MMC_READ_MULTIPLE_BLOCK &&
	    cmd->opcode != MMC_STOP_TRANSMISSION &&
	    (!metadata || metadata == -EBADMSG))
		return metadata;
	if (!cmd || !user_area || sectors != 15269888 || mrq->sbc ||
	    cmd->data != data)
		return -EPERM;
	/* Mainline read recovery sends a non-busy STOP; no HPI argument. */
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
