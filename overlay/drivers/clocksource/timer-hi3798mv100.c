// SPDX-License-Identifier: GPL-2.0-only
/*
 * Single-core diagnostic timer for Hi3798MV100.
 * Register facts and the repeated event LOAD write follow the pinned vendor
 * hisp804 reference. This driver intentionally does not enable other CPUs or
 * touch clock gates, secure registers, OTP, storage or bootloader state.
 * The upstream "hisilicon,sp804" binding describes a different 64-bit layout.
 */
#define pr_fmt(fmt) "hi3798mv100-timer: " fmt

#include <linux/clk.h>
#include <linux/clockchips.h>
#include <linux/clocksource.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/of_address.h>
#include <linux/of_clk.h>
#include <linux/of_irq.h>
#include <linux/sched_clock.h>

#include "timer-sp.h"

static void __iomem *mv100_source;
static void __iomem *mv100_event;
static unsigned long mv100_reload;

static u64 notrace mv100_sched_read(void)
{
	return (u32)~readl_relaxed(mv100_source + TIMER_VALUE);
}

static int mv100_shutdown(struct clock_event_device *evt)
{
	writel(0, mv100_event + TIMER_CTRL);
	return 0;
}

static void mv100_program(unsigned long count, unsigned long mode)
{
	writel(TIMER_CTRL_32BIT, mv100_event + TIMER_CTRL);
	/* Preserve the vendor hardware workaround until physical validation. */
	writel(count, mv100_event + TIMER_LOAD);
	writel(count, mv100_event + TIMER_LOAD);
	writel(TIMER_CTRL_32BIT | TIMER_CTRL_IE | TIMER_CTRL_ENABLE | mode,
	       mv100_event + TIMER_CTRL);
}

static int mv100_periodic(struct clock_event_device *evt)
{
	mv100_program(mv100_reload, TIMER_CTRL_PERIODIC);
	return 0;
}

static int mv100_next_event(unsigned long next, struct clock_event_device *evt)
{
	mv100_program(next, TIMER_CTRL_ONESHOT);
	return 0;
}

static struct clock_event_device mv100_clkevt = {
	.name = "hi3798mv100-cpu0",
	.rating = 400,
	.features = CLOCK_EVT_FEAT_PERIODIC | CLOCK_EVT_FEAT_ONESHOT,
	.set_state_shutdown = mv100_shutdown,
	.set_state_oneshot = mv100_shutdown,
	.set_state_periodic = mv100_periodic,
	.tick_resume = mv100_shutdown,
	.set_next_event = mv100_next_event,
};

static irqreturn_t mv100_interrupt(int irq, void *dev_id)
{
	struct clock_event_device *evt = dev_id;

	writel(1, mv100_event + TIMER_INTCLR);
	evt->event_handler(evt);
	return IRQ_HANDLED;
}

static int __init mv100_timer_init(struct device_node *node)
{
	struct clk *clk;
	unsigned long rate;
	int ret, irq;

	clk = of_clk_get(node, 0);
	if (IS_ERR(clk))
		return PTR_ERR(clk);
	ret = clk_prepare_enable(clk);
	if (ret)
		goto put_clk;
	rate = clk_get_rate(clk);
	if (!rate) {
		ret = -EINVAL;
		goto disable_clk;
	}
	mv100_source = of_iomap(node, 0);
	mv100_event = of_iomap(node, 1);
	if (!mv100_source || !mv100_event) {
		ret = -ENXIO;
		goto unmap;
	}
	irq = irq_of_parse_and_map(node, 0);
	if (irq <= 0) {
		ret = -EINVAL;
		goto unmap;
	}
	writel(0, mv100_source + TIMER_CTRL);
	writel(0, mv100_event + TIMER_CTRL);
	writel(1, mv100_event + TIMER_INTCLR);
	ret = request_irq(irq, mv100_interrupt, IRQF_TIMER,
			  mv100_clkevt.name, &mv100_clkevt);
	if (ret)
		goto unmap;

	writel(0xffffffff, mv100_source + TIMER_LOAD);
	writel(TIMER_CTRL_32BIT | TIMER_CTRL_ENABLE | TIMER_CTRL_PERIODIC,
	       mv100_source + TIMER_CTRL);
	ret = clocksource_mmio_init(mv100_source + TIMER_VALUE,
			"hi3798mv100", rate, 499, 32, clocksource_mmio_readl_down);
	if (ret) {
		writel(0, mv100_source + TIMER_CTRL);
		free_irq(irq, &mv100_clkevt);
		goto unmap;
	}
	sched_clock_register(mv100_sched_read, 32, rate);
	mv100_clkevt.irq = irq;
	mv100_clkevt.cpumask = cpumask_of(0);
	mv100_reload = DIV_ROUND_CLOSEST(rate, HZ);
	clockevents_config_and_register(&mv100_clkevt, rate, 0xf, 0x7fffffff);
	pr_info("single CPU, %lu Hz, source/event mapped, IRQ %d\n", rate, irq);
	return 0;

unmap:
	if (mv100_event)
		iounmap(mv100_event);
	if (mv100_source)
		iounmap(mv100_source);
disable_clk:
	clk_disable_unprepare(clk);
put_clk:
	clk_put(clk);
	return ret;
}
TIMER_OF_DECLARE(hi3798mv100, "hisilicon,hi3798mv100-timer", mv100_timer_init);
