/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_EMMC_RW_POLICY_H
#define HI3798MV100_EMMC_RW_POLICY_H

#include "hi3798mv100-emmc-ro-policy.h"
#include "hi3798mv100-block-rw-policy.h"

/* Production user-area I/O. Keep the installed board's p6/p9 write boundary;
 * bootloader, environment, calibration, backup, boot/RPMB and security state
 * are not ordinary system storage. Multi-block writes must stay in one range.
 */
static inline int hi3798mv100_emmc_rw_request(struct mmc_request *mrq,
					    bool user_area, u64 sectors)
{
	struct mmc_command *cmd;
	u32 switch_flags = MMC_RSP_SPI_R1B | MMC_RSP_R1B | MMC_CMD_AC;
	u32 cache_arg = (MMC_SWITCH_MODE_WRITE_BYTE << 24) |
		       (EXT_CSD_CACHE_CTRL << 16) | EXT_CSD_CMD_SET_NORMAL;
	u32 flush_arg = (MMC_SWITCH_MODE_WRITE_BYTE << 24) |
		       (EXT_CSD_FLUSH_CACHE << 16) | (1 << 8) |
		       EXT_CSD_CMD_SET_NORMAL;
	int ret;

	if (!mrq || !mrq->cmd)
		return -EPERM;
	cmd = mrq->cmd;
	/* Cache setup precedes card registration. Only this volatile byte and
	 * FLUSH_CACHE are writable; no persistent EXT_CSD settings are allowed.
	 */
	if (cmd->opcode == MMC_SWITCH && !mrq->data && !cmd->data &&
	    !mrq->stop && !mrq->sbc &&
	    (cmd->flags == switch_flags || cmd->flags ==
	     (MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_AC)) &&
	    (cmd->arg == cache_arg || cmd->arg == (cache_arg | (1 << 8)) ||
	     cmd->arg == flush_arg))
		return 0;
	ret = hi3798mv100_emmc_ro_request(mrq, user_area, sectors);
	if (!ret || cmd->opcode == MMC_SWITCH)
		return ret;
	ret = hi3798mv100_block_rw_request(mrq, user_area &&
					 sectors == 15269888, sectors);
	if (ret || !mrq->data || !(mrq->data->flags & MMC_DATA_WRITE))
		return ret;
	if ((cmd->arg >= 28672 && cmd->arg < 69632 &&
	     mrq->data->blocks <= 69632 - cmd->arg) ||
	    (cmd->arg >= 1249280 && cmd->arg < 15269888 &&
	     mrq->data->blocks <= 15269888 - cmd->arg))
		return 0;
	return -EPERM;
}

#endif
