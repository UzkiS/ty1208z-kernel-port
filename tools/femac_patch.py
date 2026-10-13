"""Checked adaptations to the pinned upstream FEMAC for inherited MV100 PHY."""

BUSY_COUNTERS = ('\t\tdev->stats.tx_dropped++;\n'
                 '\t\tdev->stats.tx_fifo_errors++;\n'
                 '\t\tnetif_stop_queue(dev);\n'
                 '\t\treturn NETDEV_TX_BUSY;\n')


def replacements():
    return [
        ('#include <linux/circ_buf.h>\n',
         '#include <linux/circ_buf.h>\n#include <linux/delay.h>\n#include <linux/timer.h>\n'),
        ('struct hisi_femac_queue {\n',
         '#include "hi3798mv100-femac.h"\n\nstruct hisi_femac_queue {\n'),
        ('\tu32 link_status;\n',
         '\tu32 link_status;\n\tbool mv100_inherited;\n\tu32 irq_mask;\n'
         '\tstruct timer_list tx_monitor;\n'),
        ('\t\tlen = rx_pkt_info & RX_FRAME_LEN_MASK;\n\t\tlen -= ETH_FCS_LEN;\n',
         '\t\tlen = rx_pkt_info & RX_FRAME_LEN_MASK;\n'),
        ('\t\tskb_put(skb, len);\n\t\tif (unlikely(skb->len > MAX_FRAME_SIZE)) {\n',
         '\t\tif (unlikely(!hi3798mv100_femac_valid_length(len))) {\n'),
        ('\t\tskb->protocol = eth_type_trans(skb, dev);\n',
         '\t\tlen -= ETH_FCS_LEN;\n\t\tskb_put(skb, len);\n'
         '\t\tskb->protocol = eth_type_trans(skb, dev);\n'),
        # RX_RDY acknowledges/pops a received descriptor. Never clear it in ISR
        # or after polling; it must remain set until hisi_femac_rx consumes it.
        ('writel(ints & DEF_INT_MASK,',
         'writel(ints & priv->irq_mask & ~IRQ_INT_RX_RDY,'),
        ('} while (ints & DEF_INT_MASK);',
         '} while (ints & (priv->mv100_inherited ? IRQ_INT_RX_RDY : priv->irq_mask));'),
        ('\tint ints, num;\n\n\tdo {\n',
         '\tint ints, num;\n\n\t/* Zero-budget NAPI may reclaim TX only. */\n'
         '\tif (unlikely(!budget)) {\n\t\thisi_femac_xmit_reclaim(dev);\n'
         '\t\treturn 0;\n\t}\n\n\tdo {\n'),
        ('\t\thisi_femac_irq_enable(priv, DEF_INT_MASK &\n'
         '\t\t\t\t\t(~IRQ_INT_TX_PER_PACKET));',
         '\t\thisi_femac_irq_enable(priv, priv->mv100_inherited ?\n'
         '\t\t\t\t      IRQ_INT_RX_RDY : priv->irq_mask &\n'
         '\t\t\t\t      (~IRQ_INT_TX_PER_PACKET));'),
        ('\tstruct hisi_femac_priv *priv = netdev_priv(dev);\n\n'
         '\tints = readl(priv->glb_base + GLB_IRQ_RAW);\n',
         '\tstruct hisi_femac_priv *priv = netdev_priv(dev);\n\n'
         '\tints = readl(priv->glb_base + (priv->mv100_inherited ?\n'
         '\t\t\t\t       GLB_IRQ_STAT : GLB_IRQ_RAW));\n'),
        ('\tif (likely(ints & DEF_INT_MASK)) {\n',
         '\tif (!(ints & priv->irq_mask))\n\t\treturn IRQ_NONE;\n\n'
         '\tif (likely(ints & priv->irq_mask)) {\n'),
        ('hisi_femac_irq_disable(priv, DEF_INT_MASK);',
         'hisi_femac_irq_disable(priv, priv->irq_mask);'),
        ('\tu32 val;\n\n\tval = readl(priv->glb_base + GLB_SOFT_RESET);',
         '\tu32 val;\n\n\tif (priv->mv100_inherited) {\n'
         '\t\thi3798mv100_femac_reset(priv->glb_base);\n\t\treturn 0;\n\t}\n\n'
         '\tval = readl(priv->glb_base + GLB_SOFT_RESET);'),
        ('static int hisi_femac_net_open(struct net_device *dev)\n',
         'static void hisi_femac_port_init(struct hisi_femac_priv *priv);\n\n' +
         TX_MONITOR +
         'static int hisi_femac_net_open(struct net_device *dev)\n'),
        ('\thisi_femac_port_reset(priv);\n\thisi_femac_set_hw_mac_addr',
         '\thisi_femac_port_reset(priv);\n\tif (priv->mv100_inherited)\n'
         '\t\thisi_femac_port_init(priv);\n\thisi_femac_set_hw_mac_addr'),
        ('hisi_femac_irq_enable(priv, IRQ_ENA_ALL | IRQ_ENA_PORT0 | DEF_INT_MASK);',
         'hisi_femac_irq_enable(priv, IRQ_ENA_ALL | IRQ_ENA_PORT0 |\n'
         '\t\t\t     (priv->mv100_inherited ? IRQ_INT_RX_RDY : priv->irq_mask));\n'
         '\tif (priv->mv100_inherited)\n'
         '\t\tmod_timer(&priv->tx_monitor, jiffies + msecs_to_jiffies(20));'),
        ('\thisi_femac_irq_disable(priv, IRQ_ENA_PORT0);\n\n\tif (dev->phydev)',
         '\thisi_femac_irq_disable(priv, IRQ_ENA_PORT0);\n'
         '\tif (priv->mv100_inherited)\n\t\tdel_timer_sync(&priv->tx_monitor);\n\n'
         '\tif (dev->phydev)'),
        ('\thisi_femac_free_skb_rings(priv);\n',
         '\t/* Stop MAC DMA before releasing buffers for this new variant. */\n'
         '\tif (priv->mv100_inherited) {\n\t\tsynchronize_irq(dev->irq);\n'
         '\t\thisi_femac_port_reset(priv);\n\t}\n'
         '\thisi_femac_free_skb_rings(priv);\n'),
        ('hisi_femac_irq_enable(priv, IRQ_INT_TX_PER_PACKET);',
         'hisi_femac_irq_enable(priv, priv->mv100_inherited ?\n'
         '\t\t\t\t      IRQ_INT_TX_FIFO_EMPTY : IRQ_INT_TX_PER_PACKET);'),
        # NETDEV_TX_BUSY leaves skb ownership with the stack. Retried packets
        # are not drops; retain the real drop accounting on DMA mapping failure.
        (BUSY_COUNTERS,
         '\t\t/* The stack retains this skb for retry. */\n'
         '\t\tnetif_stop_queue(dev);\n'
         '\t\treturn NETDEV_TX_BUSY;\n'),
        ('\tval = RX_COALESCED_TIMER |\n'
         '\t\t(RX_COALESCED_FRAMES << RX_COALESCED_FRAME_OFFSET);\n'
         '\twritel(val, priv->port_base + RX_COALESCE_SET);\n',
         '\tif (priv->mv100_inherited) {\n'
         '\t\thi3798mv100_femac_setup(priv->port_base, priv->glb_base);\n'
         '\t} else {\n\t\tval = RX_COALESCED_TIMER |\n'
         '\t\t\t(RX_COALESCED_FRAMES << RX_COALESCED_FRAME_OFFSET);\n'
         '\t\twritel(val, priv->port_base + RX_COALESCE_SET);\n\t}\n'),
        ('\tpriv->ndev = ndev;\n',
         '\tpriv->ndev = ndev;\n'
         '\tpriv->mv100_inherited = of_device_is_compatible(node,\n'
         '\t\t\t\t"hisilicon,hi3798mv100-femac-inherited");\n'
         '\tpriv->irq_mask = priv->mv100_inherited ?\n'
         '\t\t(IRQ_INT_RX_RDY | IRQ_INT_TX_FIFO_EMPTY) : DEF_INT_MASK;\n'
         '\tif (priv->mv100_inherited) {\n'
         '\t\ttimer_setup(&priv->tx_monitor, hisi_femac_mv100_tx_monitor, 0);\n'
         '\t\tret = hisi_femac_mv100_resources(pdev);\n'
         '\t\tif (ret)\n\t\t\tgoto out_free_netdev;\n'
         '\t\tret = dma_set_mask_and_coherent(dev, DMA_BIT_MASK(32));\n'
         '\t\tif (ret)\n\t\t\tgoto out_free_netdev;\n\t}\n'),
        ('\tpriv->mac_rst = devm_reset_control_get(dev, "mac");\n'
         '\tif (IS_ERR(priv->mac_rst)) {\n\t\tret = PTR_ERR(priv->mac_rst);\n'
         '\t\tgoto out_disable_clk;\n\t}\n\thisi_femac_core_reset(priv);\n',
         '\tif (priv->mv100_inherited) {\n'
         '\t\tret = hisi_femac_mv100_phy_ready(node);\n'
         '\t\tif (ret)\n\t\t\tgoto out_disable_clk;\n'
         '\t\thisi_femac_port_reset(priv);\n'
         '\t} else {\n\t\tpriv->mac_rst = devm_reset_control_get(dev, "mac");\n'
         '\t\tif (IS_ERR(priv->mac_rst)) {\n\t\t\tret = PTR_ERR(priv->mac_rst);\n'
         '\t\t\tgoto out_disable_clk;\n\t\t}\n\t\thisi_femac_core_reset(priv);\n\t}\n'),
        ('static int hisi_femac_drv_probe(struct platform_device *pdev)\n',
         HELPERS + 'static int hisi_femac_drv_probe(struct platform_device *pdev)\n'),
        ('\t{.compatible = "hisilicon,hisi-femac-v1",},\n',
         '\t{.compatible = "hisilicon,hi3798mv100-femac-inherited",},\n'
         '\t{.compatible = "hisilicon,hisi-femac-v1",},\n'),
    ]


# These anchors intentionally occur twice (ISR/poll and both queue-full paths).
REPEATED_ANCHORS = {
    "writel(ints & DEF_INT_MASK,": 2,
    "hisi_femac_irq_enable(priv, IRQ_INT_TX_PER_PACKET);": 2,
    BUSY_COUNTERS: 2,
}

TX_MONITOR = '''/* The SDK uses a periodic monitor to reclaim transmit buffers.
 * TX-ready is a credit notification, not a per-packet completion interrupt.
 * Schedule NAPI so all reclamation retains the upstream locking/DMA path.
 */
static void hisi_femac_mv100_tx_monitor(struct timer_list *timer)
{
	struct hisi_femac_priv *priv = from_timer(priv, timer, tx_monitor);

	if (!netif_running(priv->ndev))
		return;
	if (READ_ONCE(priv->tx_fifo_used_cnt))
		napi_schedule(&priv->napi);
	mod_timer(&priv->tx_monitor, jiffies + msecs_to_jiffies(20));
}

'''

HELPERS = '''/* Explicit board experiment: no generic PHY reset fallback. */
static int hisi_femac_mv100_phy_ready(struct device_node *node)
{
	struct device_node *phynode;
	struct phy_device *phy;
	int ret = 0;

	phynode = of_parse_phandle(node, "phy-handle", 0);
	if (!phynode)
		return -EINVAL;
	phy = of_phy_find_device(phynode);
	of_node_put(phynode);
	if (!phy)
		return -EPROBE_DEFER;
	if (phy->mdio.addr != 1 || phy->phy_id != 0x20669823)
		ret = -ENODEV;
	else if (!phy->drv || strcmp(phy->drv->name, "TY1208Z FESTAv220 inherited"))
		ret = -EPROBE_DEFER;
	put_device(&phy->mdio.dev);
	return ret;
}

static int hisi_femac_mv100_resources(struct platform_device *pdev)
{
	static const resource_size_t addresses[] = { 0xf9840000, 0xf9841300 };
	static const resource_size_t sizes[] = { 0x400, 0x200 };
	struct resource *res;
	unsigned int i;

	if (!of_machine_is_compatible("tianyi,ty1208z-ca-diagnostic") &&
	    !of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-net") &&
	    !of_machine_is_compatible("tianyi,ty1208z-ca-openwrt-router-ram"))
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(addresses); i++) {
		res = platform_get_resource(pdev, IORESOURCE_MEM, i);
		if (!res || res->start != addresses[i] || resource_size(res) != sizes[i])
			return -EINVAL;
	}
	if (platform_get_resource(pdev, IORESOURCE_MEM, ARRAY_SIZE(addresses)))
		return -EINVAL;
	if (of_property_read_bool(pdev->dev.of_node, "resets") ||
	    of_property_read_bool(pdev->dev.of_node, PHY_RESET_DELAYS_PROPERTY))
		return -EINVAL;
	return 0;
}

'''
