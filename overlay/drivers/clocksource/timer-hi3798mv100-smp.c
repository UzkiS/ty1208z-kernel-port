// SPDX-License-Identifier: GPL-2.0-only
/*
 * Hi3798MV100 four-core local timer.
 *
 * The register layout and IRQ order are taken from the public HiSilicon
 * hisp804 driver: one free-running source at 0xf8a29000 followed by local
 * timers at 0xf8a2a000, 0xf8a2a020, 0xf8a2b000 and 0xf8a2b020.  This driver
 * is selected only by the explicit SMP profile; the older two-resource
 * diagnostic timer remains unchanged for UP images.
 */
#define pr_fmt(fmt) "hi3798mv100-smp-timer: " fmt

#include <linux/clk.h>
#include <linux/clockchips.h>
#include <linux/clocksource.h>
#include <linux/cpuhotplug.h>
#include <linux/err.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/of_clk.h>
#include <linux/of_irq.h>
#include <linux/percpu.h>
#include <linux/sched_clock.h>

#include "timer-sp.h"

struct mv100_smp_event {
	struct clock_event_device clkevt;
	void __iomem *base;
	unsigned long rate;
	unsigned long reload;
	unsigned int irq;
	bool requested;
};

static struct mv100_smp_event __percpu *mv100_events;
static unsigned int mv100_event_count;
static void __iomem *mv100_source;
static void __iomem *mv100_sched_base;
static struct clocksource mv100_smp_clksrc;

static u64 notrace mv100_smp_sched_read(void)
{
	return ~readl_relaxed(mv100_sched_base + TIMER_VALUE);
}

static u64 mv100_smp_clocksource_read(struct clocksource *cs)
{
	return ~readl_relaxed(mv100_source + TIMER_VALUE);
}

static inline struct mv100_smp_event *to_mv100_event(
		struct clock_event_device *evt)
{
	return container_of(evt, struct mv100_smp_event, clkevt);
}

static int mv100_smp_shutdown(struct clock_event_device *evt)
{
	struct mv100_smp_event *event = to_mv100_event(evt);

	writel(0, event->base + TIMER_CTRL);
	return 0;
}

static int mv100_smp_set_next(unsigned long next,
				      struct clock_event_device *evt)
{
	struct mv100_smp_event *event = to_mv100_event(evt);

	writel(TIMER_CTRL_32BIT, event->base + TIMER_CTRL);
	/* The second LOAD write is required by the vendor hardware workaround. */
	writel(next, event->base + TIMER_LOAD);
	writel(next, event->base + TIMER_LOAD);
	writel(TIMER_CTRL_32BIT | TIMER_CTRL_IE | TIMER_CTRL_ONESHOT |
	       TIMER_CTRL_ENABLE, event->base + TIMER_CTRL);
	return 0;
}

static int mv100_smp_set_periodic(struct clock_event_device *evt)
{
	struct mv100_smp_event *event = to_mv100_event(evt);

	writel(TIMER_CTRL_32BIT, event->base + TIMER_CTRL);
	writel(event->reload, event->base + TIMER_LOAD);
	writel(event->reload, event->base + TIMER_LOAD);
	writel(TIMER_CTRL_32BIT | TIMER_CTRL_IE | TIMER_CTRL_PERIODIC |
	       TIMER_CTRL_ENABLE, event->base + TIMER_CTRL);
	return 0;
}

static irqreturn_t mv100_smp_interrupt(int irq, void *dev_id)
{
	struct mv100_smp_event *event = dev_id;

	writel(1, event->base + TIMER_INTCLR);
	event->clkevt.event_handler(&event->clkevt);
	return IRQ_HANDLED;
}

static int mv100_smp_cpu_starting(unsigned int cpu)
{
	struct mv100_smp_event *event;

	if (cpu >= mv100_event_count)
		return -EINVAL;
	event = per_cpu_ptr(mv100_events, cpu);
	irq_force_affinity(event->irq, cpumask_of(cpu));
	clockevents_config_and_register(&event->clkevt, event->rate, 0xf,
					0x7fffffff);
	return 0;
}

static int mv100_smp_cpu_dying(unsigned int cpu)
{
	if (cpu < mv100_event_count)
		mv100_smp_shutdown(&per_cpu_ptr(mv100_events, cpu)->clkevt);
	return 0;
}

static void mv100_smp_source_enable(void __iomem *base)
{
	writel(0, base + TIMER_CTRL);
	writel(0xffffffff, base + TIMER_LOAD);
	writel(0xffffffff, base + TIMER_VALUE);
	writel(TIMER_CTRL_32BIT | TIMER_CTRL_ENABLE | TIMER_CTRL_PERIODIC,
	       base + TIMER_CTRL);
}

static int __init mv100_smp_timer_init(struct device_node *node)
{
	struct clk *clk;
	unsigned long rate, reload;
	unsigned int i;
	int ret, irq, hotplug_state;

	if (!IS_ENABLED(CONFIG_SMP))
		return -ENODEV;
	mv100_event_count = min_t(unsigned int, of_irq_count(node), nr_cpu_ids);
	if (!mv100_event_count || of_address_count(node) != of_irq_count(node) + 1)
		return -EINVAL;

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
	reload = DIV_ROUND_CLOSEST(rate, HZ);

	mv100_events = alloc_percpu(struct mv100_smp_event);
	if (!mv100_events) {
		ret = -ENOMEM;
		goto disable_clk;
	}
	mv100_source = of_iomap(node, 0);
	if (!mv100_source) {
		ret = -ENXIO;
		goto free_events;
	}
	mv100_sched_base = mv100_source;
	mv100_smp_source_enable(mv100_source);
	for (i = 0; i < mv100_event_count; i++) {
		struct mv100_smp_event *event = per_cpu_ptr(mv100_events, i);

		event->base = NULL;
		event->irq = 0;
		event->base = of_iomap(node, i + 1);
		if (!event->base) {
			ret = -ENXIO;
			goto free_irqs;
		}
		irq = irq_of_parse_and_map(node, i);
		if (irq <= 0) {
			ret = -EINVAL;
			goto free_irqs;
		}
		event->irq = irq;
		event->rate = rate;
		event->reload = reload;
		event->clkevt.name = "hi3798mv100-local-timer";
		event->clkevt.rating = 400;
		event->clkevt.features = CLOCK_EVT_FEAT_PERIODIC |
			CLOCK_EVT_FEAT_ONESHOT;
		event->clkevt.set_state_shutdown = mv100_smp_shutdown;
		event->clkevt.set_state_oneshot = mv100_smp_shutdown;
		event->clkevt.set_state_periodic = mv100_smp_set_periodic;
		event->clkevt.set_next_event = mv100_smp_set_next;
		event->clkevt.tick_resume = mv100_smp_shutdown;
		event->clkevt.irq = irq;
		event->clkevt.cpumask = cpumask_of(i);
		writel(0, event->base + TIMER_CTRL);
		writel(1, event->base + TIMER_INTCLR);
		ret = request_irq(irq, mv100_smp_interrupt,
				  IRQF_TIMER | IRQF_NOBALANCING,
				  event->clkevt.name, event);
		if (ret)
			goto free_irqs;
		event->requested = true;
	}

	mv100_smp_clksrc.name = "hi3798mv100-smp";
	mv100_smp_clksrc.rating = 499;
	mv100_smp_clksrc.read = mv100_smp_clocksource_read;
	mv100_smp_clksrc.mask = CLOCKSOURCE_MASK(32);
	mv100_smp_clksrc.flags = CLOCK_SOURCE_IS_CONTINUOUS;
	ret = clocksource_register_hz(&mv100_smp_clksrc, rate);
	if (ret)
		goto free_irqs;

	hotplug_state = cpuhp_setup_state(CPUHP_AP_HI3798MV100_TIMER_STARTING,
					  "clockevents/hi3798mv100-smp:online",
					  mv100_smp_cpu_starting, mv100_smp_cpu_dying);
	if (hotplug_state < 0) {
		ret = hotplug_state;
		clocksource_unregister(&mv100_smp_clksrc);
		goto free_irqs;
	}
	pr_info("four local timers, %lu Hz, %u CPUs\n", rate, mv100_event_count);
	sched_clock_register(mv100_smp_sched_read, 32, rate);
	return 0;

free_irqs:
	for (i = 0; i < mv100_event_count; i++) {
		struct mv100_smp_event *event = per_cpu_ptr(mv100_events, i);

		if (event->requested)
			free_irq(event->irq, event);
		if (event->irq)
			irq_dispose_mapping(event->irq);
		if (event->base)
			iounmap(event->base);
	}
	if (mv100_source)
		writel(0, mv100_source + TIMER_CTRL);
	if (mv100_source)
		iounmap(mv100_source);
free_events:
	free_percpu(mv100_events);
disable_clk:
	clk_disable_unprepare(clk);
put_clk:
	clk_put(clk);
	return ret;
}

TIMER_OF_DECLARE(hi3798mv100_smp, "hisilicon,hisp804", mv100_smp_timer_init);
