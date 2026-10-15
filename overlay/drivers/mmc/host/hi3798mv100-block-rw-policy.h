/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_BLOCK_RW_POLICY_H
#define HI3798MV100_BLOCK_RW_POLICY_H

#include <linux/errno.h>
#include <linux/mmc/core.h>
#include <linux/mmc/mmc.h>

/* Ordinary legacy block I/O. The DW host supplies the queue/SG byte limits;
 * 65535 is its normal maximum block count, rather than a diagnostic page cap.
 * No CMD23, reliable-write, erase, partition switch or vendor operation.
 */
static inline int hi3798mv100_block_rw_request(struct mmc_request *mrq,
					     bool addressed, u64 sectors)
{
	struct mmc_command *cmd;
	struct mmc_data *data;
	u32 flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
	u32 read_stop = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC;
	u32 write_stop = MMC_RSP_SPI_R1B | MMC_RSP_R1B | MMC_CMD_AC;
	bool write;

	if (!mrq || !mrq->cmd || !addressed || !sectors ||
	    sectors > (1ULL << 32) || mrq->sbc)
		return -EPERM;
	cmd = mrq->cmd;
	data = mrq->data;
	if (cmd->data != data)
		return -EPERM;
	if (cmd->opcode == MMC_STOP_TRANSMISSION && !data && !mrq->stop)
		return !cmd->arg && (cmd->flags == read_stop ||
				   cmd->flags == write_stop) ? 0 : -EPERM;
	if (!data || data->blksz != 512 || !data->blocks ||
	    data->blocks > 65535 || cmd->flags != flags ||
	    cmd->arg >= sectors || data->blocks > sectors - cmd->arg)
		return -EPERM;
	/* MMC_DATA_DAT_TAG is a software hint from REQ_META. With no CMD23
	 * capability it changes no command on the wire; retain ordinary writes.
	 */
	write = data->flags == MMC_DATA_WRITE ||
		data->flags == (MMC_DATA_WRITE | MMC_DATA_DAT_TAG);
	if (!write && data->flags != MMC_DATA_READ)
		return -EPERM;
	if (data->blocks == 1)
		return cmd->opcode == (write ? MMC_WRITE_BLOCK :
			MMC_READ_SINGLE_BLOCK) && !mrq->stop && !data->stop ?
			0 : -EPERM;
	if (cmd->opcode != (write ? MMC_WRITE_MULTIPLE_BLOCK :
			    MMC_READ_MULTIPLE_BLOCK) || !mrq->stop ||
	    data->stop != mrq->stop ||
	    mrq->stop->opcode != MMC_STOP_TRANSMISSION ||
	    mrq->stop->arg || mrq->stop->data ||
	    mrq->stop->flags != (write ? write_stop : read_stop))
		return -EPERM;
	return 0;
}

#endif
