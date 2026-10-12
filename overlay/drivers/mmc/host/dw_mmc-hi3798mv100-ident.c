// SPDX-License-Identifier: GPL-2.0-only
/* Restricted RAM diagnostic, not the production MV100 storage driver. */
#include <linux/io.h>
#include <linux/irq.h>
#include <linux/mmc/host.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include "dw_mmc.h"
#include "dw_mmc-pltfm.h"
#include "hi3798mv100-ident-policy.h"

static int mv100_ident_init(struct dw_mci *host)
{
	if (host->bus_hz != 100000000 || host->pdata->fifo_depth != 256 ||
	    mci_readl(host, VERID) != 0x5342270a ||
	    mci_readl(host, HCON) != 0x00e44c81)
		return -ENODEV;

	/* PIO bypasses dw_mci_idmac_init(), including its inherited-IRQ cleanup.
	 * Quiesce the measured 32-bit IDMAC before request_irq enables the GIC line.
	 * This changes only controller state, not card settings or storage contents.
	 */
	dev_info(host->dev,
		 "EMMC_IDENT_INHERITED CTRL=%08x BMOD=%08x IDINTEN=%08x IDSTS=%08x RINTSTS=%08x\n",
		 mci_readl(host, CTRL), mci_readl(host, BMOD),
		 mci_readl(host, IDINTEN), mci_readl(host, IDSTS),
		 mci_readl(host, RINTSTS));
	mci_writel(host, INTMASK, 0);
	mci_writel(host, IDINTEN, 0);
	mci_writel(host, BMOD, mci_readl(host, BMOD) & ~SDMMC_IDMAC_ENABLE);
	mci_writel(host, CTRL, mci_readl(host, CTRL) &
		   ~(SDMMC_CTRL_INT_ENABLE | SDMMC_CTRL_DMA_ENABLE |
		     SDMMC_CTRL_USE_IDMAC));
	mci_writel(host, IDSTS, SDMMC_IDMAC_INT_AI | SDMMC_IDMAC_INT_NI |
		   SDMMC_IDMAC_INT_CES | SDMMC_IDMAC_INT_DU |
		   SDMMC_IDMAC_INT_FBE | SDMMC_IDMAC_INT_RI | SDMMC_IDMAC_INT_TI);
	mci_writel(host, RINTSTS, 0xffffffff);
	dev_info(host->dev,
		 "EMMC_IDENT_PIO_QUIESCED CTRL=%08x BMOD=%08x IDINTEN=%08x IDSTS=%08x\n",
		 mci_readl(host, CTRL), mci_readl(host, BMOD),
		 mci_readl(host, IDINTEN), mci_readl(host, IDSTS));

	dev_info(host->dev, "EMMC_IDENT_GUARD_PASS source=100000000 PIO-only\n");
	return 0;
}

static int mv100_ident_slot(struct dw_mci_slot *slot)
{
	struct mmc_host *mmc = slot->mmc;

	/* Override all DT/core capabilities before mmc_add_host can enumerate. */
	mmc->caps = MMC_CAP_NONREMOVABLE;
	mmc->caps2 = MMC_CAP2_NO_SD | MMC_CAP2_NO_SDIO;
	mmc->pm_caps = 0;
	mmc->f_max = 25000000;
	mmc->max_blk_size = 512;
	mmc->max_blk_count = 1;
	mmc->max_req_size = 512;
	mmc->max_seg_size = 512;
	mmc->dsr_req = 0;
	return 0;
}

static int mv100_ident_validate(struct dw_mci *host, struct mmc_request *mrq)
{
	int ret = hi3798mv100_ident_request(mrq);

	if (ret)
		dev_info_ratelimited(host->dev,
			"EMMC_IDENT_BLOCKED CMD%u arg=%08x error=%d\n",
			mrq->cmd->opcode, mrq->cmd->arg, ret);
	else if (mrq->cmd->opcode == MMC_SEND_OP_COND)
		dev_info_ratelimited(host->dev, "EMMC_IDENT_CMD1 arg=%08x\n",
				     mrq->cmd->arg);
	return ret;
}

static int mv100_ident_voltage(struct mmc_host *mmc, struct mmc_ios *ios)
{
	/* Retain the inherited I/O voltage; never change regulators/UHS voltage. */
	return ios->signal_voltage == MMC_SIGNAL_VOLTAGE_330 ? 0 : -EPERM;
}

static const struct dw_mci_drv_data mv100_ident_data = {
	.init = mv100_ident_init,
	.init_slot = mv100_ident_slot,
	.validate_request = mv100_ident_validate,
	.switch_voltage = mv100_ident_voltage,
	.force_pio = true,
};

static int mv100_ident_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct resource *controller, *crg;
	struct irq_data *irq_data;
	void __iomem *regs, *crg40;
	u32 value;
	int irq;

	controller = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	crg = platform_get_resource(pdev, IORESOURCE_MEM, 1);
	if (!controller || controller->start != 0xf9830000 ||
	    resource_size(controller) != 0x1000 || !crg ||
	    crg->start != 0xf8a220a0 || resource_size(crg) != 4)
		return -EINVAL;

	irq = platform_get_irq(pdev, 0);
	if (irq < 0)
		return irq;
	irq_data = irq_get_irq_data(irq);
	if (!irq_data || irq_data->hwirq != 67)
		return -EINVAL;

	/* Inherit measured pinmux/CRG; no clock/reset/power provider is called. */
	if (of_find_property(dev->of_node, "clocks", NULL) ||
	    of_find_property(dev->of_node, "resets", NULL) ||
	    of_find_property(dev->of_node, "mmc-pwrseq", NULL) ||
	    of_find_property(dev->of_node, "vmmc-supply", NULL) ||
	    of_find_property(dev->of_node, "vqmmc-supply", NULL))
		return -EINVAL;

	crg40 = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(crg40))
		return PTR_ERR(crg40);
	value = readl(crg40);
	if (value != 0x00040103)
		return dev_err_probe(dev, -ENODEV, "Unexpected inherited CRG40=%08x\n", value);

	/* Check the measured identity before the generic driver can write MMIO. */
	regs = devm_ioremap(dev, controller->start, resource_size(controller));
	if (!regs)
		return -ENOMEM;
	value = readl(regs + SDMMC_VERID);
	if (value != 0x5342270a || readl(regs + SDMMC_HCON) != 0x00e44c81) {
		devm_iounmap(dev, regs);
		return -ENODEV;
	}
	devm_iounmap(dev, regs);

	return dw_mci_pltfm_register(pdev, &mv100_ident_data);
}

static const struct of_device_id mv100_ident_match[] = {
	{ .compatible = "tianyi,ty1208z-emmc-identification" },
	{ }
};
MODULE_DEVICE_TABLE(of, mv100_ident_match);

static struct platform_driver mv100_ident_driver = {
	.probe = mv100_ident_probe,
	.remove_new = dw_mci_pltfm_remove,
	.driver = {
		.name = "hi3798mv100-emmc-ident",
		.of_match_table = mv100_ident_match,
	},
};
module_platform_driver(mv100_ident_driver);
MODULE_DESCRIPTION("TY1208Z restricted PIO eMMC identification diagnostic");
MODULE_LICENSE("GPL");
