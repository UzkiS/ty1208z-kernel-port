// SPDX-License-Identifier: GPL-2.0-only
/* Fixed four-sector RAM diagnostic. No block interface or card-setting writes. */
#include <linux/crc32.h>
#include <linux/mmc/card.h>
#include <linux/mmc/core.h>
#include <linux/mmc/host.h>
#include <linux/mmc/mmc.h>
#include <linux/mmc/ty1208z-samples.h>
#include <linux/module.h>
#include <linux/scatterlist.h>
#include <linux/slab.h>
#include <linux/unaligned.h>

#include "core.h"
#include "bus.h"

static int ty1208z_read_sector(struct mmc_card *card, u32 sector, u8 *buffer)
{
	struct mmc_request mrq = {};
	struct mmc_command cmd = {};
	struct mmc_data data = {};
	struct scatterlist sg;

	if (!ty1208z_sample_sector(sector))
		return -EPERM;
	cmd.opcode = MMC_READ_SINGLE_BLOCK;
	cmd.arg = sector;
	cmd.flags = MMC_RSP_R1 | MMC_CMD_ADTC;
	cmd.data = &data;
	data.blksz = 512;
	data.blocks = 1;
	data.flags = MMC_DATA_READ;
	sg_init_one(&sg, buffer, 512);
	data.sg = &sg;
	data.sg_len = 1;
	mmc_set_data_timeout(&data, card);
	mrq.cmd = &cmd;
	mrq.data = &data;
	mmc_wait_for_req(card->host, &mrq);
	if (cmd.error || data.error)
		return cmd.error ? cmd.error : data.error;
	if (data.bytes_xfered != 512 || R1_STATUS(cmd.resp[0]))
		return -EIO;
	dev_info(&card->dev, "EMMC_SAMPLE_SECTOR lba=%u crc32=%08x\n",
		 sector, crc32_le(~0U, buffer, 512) ^ ~0U);
	return 0;
}

static int ty1208z_samples_probe(struct mmc_card *card)
{
	u8 *buffer;
	u32 first_crc, block_shift;
	int ret;

	/* Never change the selected partition or issue a sector on a different card. */
	if (!mmc_card_mmc(card) || !mmc_card_is_blockaddr(card) ||
	    strcmp(card->cid.prod_name, "008G30") || card->cid.manfid != 0x11 ||
	    card->ext_csd.sectors != 15269888 || (card->ext_csd.part_config & 7) ||
	    card->host->ios.bus_width != MMC_BUS_WIDTH_1 ||
	    card->host->ios.timing != MMC_TIMING_LEGACY ||
	    card->host->ios.clock > 25000000)
		return -ENODEV;
	buffer = kmalloc(1024, GFP_KERNEL);
	if (!buffer)
		return -ENOMEM;

	mmc_claim_host(card->host);
	ret = ty1208z_read_sector(card, TY1208Z_SAMPLE_KERNEL, buffer);
	if (ret)
		goto out;
	first_crc = crc32_le(~0U, buffer, 512) ^ ~0U;
	if (first_crc != 0x2ba1a125 || get_unaligned_be32(buffer) != 0x27051956 ||
	    get_unaligned_be32(buffer + 16) != 0x02000000 ||
	    get_unaligned_be32(buffer + 20) != 0x02000000) {
		ret = -EBADMSG;
		goto out;
	}
	ret = ty1208z_read_sector(card, TY1208Z_SAMPLE_KERNEL + 1, buffer + 512);
	if (ret)
		goto out;
	dev_info(&card->dev, "EMMC_SAMPLE_HINAS_HEADER_MATCH crc32=%08x\n", first_crc);
	ret = ty1208z_read_sector(card, TY1208Z_SAMPLE_EXT4, buffer);
	if (ret)
		goto out;
	ret = ty1208z_read_sector(card, TY1208Z_SAMPLE_EXT4 + 1, buffer + 512);
	if (ret)
		goto out;
	block_shift = get_unaligned_le32(buffer + 24);
	if (get_unaligned_le16(buffer + 56) != 0xef53 || block_shift > 6 ||
	    !get_unaligned_le32(buffer) || !get_unaligned_le32(buffer + 4)) {
		ret = -EBADMSG;
		goto out;
	}
	dev_info(&card->dev, "EMMC_SAMPLE_EXT4 magic=ef53 block_size=%u\n",
		 1024U << block_shift);
	dev_info(&card->dev, "EMMC_SAMPLE_READ_COMPLETE count=4 no-block-device\n");
out:
	mmc_release_host(card->host);
	kfree(buffer);
	if (ret)
		dev_err(&card->dev, "EMMC_SAMPLE_READ_FAILED error=%d\n", ret);
	return ret;
}

static void ty1208z_samples_remove(struct mmc_card *card)
{
}

static struct mmc_driver ty1208z_samples_driver = {
	.drv = { .name = "ty1208z-fixed-read-samples" },
	.probe = ty1208z_samples_probe,
	.remove = ty1208z_samples_remove,
};

module_driver(ty1208z_samples_driver, mmc_register_driver, mmc_unregister_driver);
MODULE_DESCRIPTION("TY1208Z fixed read-only Hinas header/superblock RAM diagnostic");
MODULE_LICENSE("GPL");
