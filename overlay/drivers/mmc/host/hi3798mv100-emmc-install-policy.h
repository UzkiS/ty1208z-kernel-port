/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_EMMC_INSTALL_POLICY_H
#define HI3798MV100_EMMC_INSTALL_POLICY_H

#include "hi3798mv100-emmc-ro-policy.h"

/* Opt-in installation kernel only. Never permit bootloader, bootargs, other
 * user-area partitions, boot/RPMB switching, erase or unknown card commands.
 * A single sector avoids enabling unmeasured CMD23/reliable-write paths.
 */
static inline int hi3798mv100_emmc_install_request(struct mmc_request *mrq,
						bool user_area, u64 sectors)
{
	struct mmc_command *cmd;
	struct mmc_data *data;
	u32 write_flags = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
	u32 flush_flags = MMC_RSP_SPI_R1B | MMC_RSP_R1B | MMC_CMD_AC;
	u32 flush_arg = (MMC_SWITCH_MODE_WRITE_BYTE << 24) |
			(EXT_CSD_FLUSH_CACHE << 16) | (1 << 8);
	u32 cache_arg = (MMC_SWITCH_MODE_WRITE_BYTE << 24) |
			(EXT_CSD_CACHE_CTRL << 16);
	int ret = hi3798mv100_emmc_ro_request(mrq, user_area, sectors);

	if (!ret || !mrq || !mrq->cmd)
		return ret;
	cmd = mrq->cmd;
	data = mrq->data;
	if (!user_area || sectors != 15269888 || mrq->sbc || mrq->stop ||
	    cmd->data != data)
		return -EPERM;
	/* Mainline may enable its volatile cache; permit only that byte's 0/1
	 * values and the flush operation needed for fsync/shutdown durability.
	 */
	if (cmd->opcode == MMC_SWITCH && !data &&
	    (cmd->arg == flush_arg || cmd->arg == cache_arg ||
	     cmd->arg == (cache_arg | (1 << 8))) &&
	    cmd->flags == flush_flags)
		return 0;
	if (cmd->opcode != MMC_WRITE_BLOCK || cmd->flags != write_flags ||
	    !data || data->flags != MMC_DATA_WRITE || data->blksz != 512 ||
	    data->blocks != 1 || data->stop)
		return ret;
	/* p6: [14,34) MiB; p9: [610,7456) MiB; all values are 512-byte sectors. */
	if ((cmd->arg >= 28672 && cmd->arg < 69632) ||
	    (cmd->arg >= 1249280 && cmd->arg < 15269888))
		return 0;
	return -EPERM;
}

#endif
