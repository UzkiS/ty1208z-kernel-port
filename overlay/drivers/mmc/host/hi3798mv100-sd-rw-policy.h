/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef HI3798MV100_SD_RW_POLICY_H
#define HI3798MV100_SD_RW_POLICY_H

#include "hi3798mv100-sd-ro-policy.h"
#include "hi3798mv100-block-rw-policy.h"

/* Production SDHC/SDXC sectors, including normal multi-block reads/writes.
 * No erase, write-protect, lock, bus/voltage changes or vendor commands.
 */
static inline int hi3798mv100_sd_rw_request(struct mmc_request *mrq,
					 bool sector_addressed, u64 sectors)
{
	if (!mrq)
		return -EPERM;
	if (!hi3798mv100_sd_ident_request(mrq))
		return 0;
	return hi3798mv100_block_rw_request(mrq, sector_addressed, sectors);
}

#endif
