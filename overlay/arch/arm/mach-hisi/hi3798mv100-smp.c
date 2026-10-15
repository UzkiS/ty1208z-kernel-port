// SPDX-License-Identifier: GPL-2.0-only
/*
 * Hi3798MV100 SMP bring-up.
 *
 * This is the Linux 6.12 form of the public HiSilicon mach-hi3798mx
 * sequence.  CPU1..3 are released through the SRAM vector at 0xffff0000,
 * then the CPU low-power selector and the three documented reset fields at
 * CRG 0xf8a22050 are changed in the vendor order.  No guessed PMU, mailbox,
 * OTP or security-state register is used.
 */
#include <linux/bitops.h>
#include <linux/delay.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/smp.h>
#include <linux/spinlock.h>

#include <asm/smp_plat.h>
#include <asm/memory.h>

#define HI3798MV100_NR_CPUS		4
#define HI3798MV100_SRAM_VECTOR		0xffff0000
#define HI3798MV100_CPU_LP		0xf8a22048
#define HI3798MV100_CPU_RESET		0xf8a22050
#define HI3798MV100_CPU_SW_BEGIN		10
#define HI3798MV100_ARM_POR_SRST		12
#define HI3798MV100_ARM_SRST		16
#define HI3798MV100_CLUSTER_DBG_SRST	20

static void __iomem *hi3798mv100_sram_vector;
static void __iomem *hi3798mv100_cpu_lp;
static void __iomem *hi3798mv100_cpu_reset;
static DEFINE_SPINLOCK(hi3798mv100_boot_lock);

static void hi3798mv100_set_boot_vector(void)
{
	writel_relaxed(0xe51ff004, hi3798mv100_sram_vector);
	writel_relaxed(__pa_symbol(secondary_startup),
		       hi3798mv100_sram_vector + 4);
	/* Ensure the SRAM instruction fetch sees both words before the IPI. */
	__iowmb();
}

static void hi3798mv100_release_reset(unsigned int cpu)
{
	u32 value;

	value = readl_relaxed(hi3798mv100_cpu_reset);
	value &= ~BIT(cpu + HI3798MV100_ARM_POR_SRST);
	writel_relaxed(value, hi3798mv100_cpu_reset);

	value = readl_relaxed(hi3798mv100_cpu_reset);
	value &= ~BIT(cpu + HI3798MV100_CLUSTER_DBG_SRST);
	writel_relaxed(value, hi3798mv100_cpu_reset);

	value = readl_relaxed(hi3798mv100_cpu_reset);
	value &= ~BIT(cpu + HI3798MV100_ARM_SRST);
	writel_relaxed(value, hi3798mv100_cpu_reset);
	__iowmb();
}

static int hi3798mv100_boot_secondary(unsigned int cpu,
					      struct task_struct *idle)
{
	unsigned long flags;
	u32 saved_lp, value;

	if (cpu == 0 || cpu >= HI3798MV100_NR_CPUS ||
	    !hi3798mv100_sram_vector || !hi3798mv100_cpu_lp ||
	    !hi3798mv100_cpu_reset)
		return -ENXIO;

	spin_lock_irqsave(&hi3798mv100_boot_lock, flags);
	hi3798mv100_set_boot_vector();

	/* Public SDK selects 400MHz while the secondary reset is released. */
	saved_lp = readl_relaxed(hi3798mv100_cpu_lp);
	writel_relaxed(0x306, hi3798mv100_cpu_lp);
	writel_relaxed(0x706, hi3798mv100_cpu_lp);
	hi3798mv100_release_reset(cpu);

	/* Restore the exact inherited low-power selector and its SW_BEGIN bit. */
	value = saved_lp & ~BIT(HI3798MV100_CPU_SW_BEGIN);
	writel_relaxed(value, hi3798mv100_cpu_lp);
	writel_relaxed(saved_lp, hi3798mv100_cpu_lp);
	__iowmb();
	spin_unlock_irqrestore(&hi3798mv100_boot_lock, flags);

	arch_send_wakeup_ipi_mask(cpumask_of(cpu));
	return 0;
}

#ifdef CONFIG_HOTPLUG_CPU
static int hi3798mv100_cpu_kill(unsigned int cpu)
{
	u32 value;

	if (cpu == 0 || cpu >= HI3798MV100_NR_CPUS || !hi3798mv100_cpu_reset)
		return 0;
	value = readl_relaxed(hi3798mv100_cpu_reset);
	value |= BIT(cpu + HI3798MV100_ARM_SRST);
	writel_relaxed(value, hi3798mv100_cpu_reset);
	value = readl_relaxed(hi3798mv100_cpu_reset);
	value |= BIT(cpu + HI3798MV100_CLUSTER_DBG_SRST);
	writel_relaxed(value, hi3798mv100_cpu_reset);
	value = readl_relaxed(hi3798mv100_cpu_reset);
	value |= BIT(cpu + HI3798MV100_ARM_POR_SRST);
	writel_relaxed(value, hi3798mv100_cpu_reset);
	__iowmb();
	return 1;
}
#endif

static void __init hi3798mv100_smp_prepare_cpus(unsigned int max_cpus)
{
	hi3798mv100_sram_vector = ioremap(HI3798MV100_SRAM_VECTOR, PAGE_SIZE);
	hi3798mv100_cpu_lp = ioremap(HI3798MV100_CPU_LP, sizeof(u32));
	hi3798mv100_cpu_reset = ioremap(HI3798MV100_CPU_RESET, sizeof(u32));
	if (!hi3798mv100_sram_vector || !hi3798mv100_cpu_lp ||
	    !hi3798mv100_cpu_reset)
		pr_err("SMP MMIO mapping failed; secondary CPUs remain offline\n");
}

static void __init hi3798mv100_smp_init_cpus(void)
{
	unsigned int i, ncores;
	u32 scu_cfg;

	asm volatile("mrc p15, 1, %0, c9, c0, 2" : "=r" (scu_cfg));
	ncores = ((scu_cfg >> 24) & 0x3) + 1;
	if (ncores > HI3798MV100_NR_CPUS)
		ncores = HI3798MV100_NR_CPUS;
	for (i = 0; i < ncores; i++)
		set_cpu_possible(i, true);
	pr_info("SMP reports %u Cortex-A7 cores\n", ncores);
}

static const struct smp_operations hi3798mv100_smp_ops __initconst = {
	.smp_init_cpus = hi3798mv100_smp_init_cpus,
	.smp_prepare_cpus = hi3798mv100_smp_prepare_cpus,
	.smp_boot_secondary = hi3798mv100_boot_secondary,
#ifdef CONFIG_HOTPLUG_CPU
	.cpu_kill = hi3798mv100_cpu_kill,
#endif
};

CPU_METHOD_OF_DECLARE(hi3798mv100_smp, "hisilicon,hi3798mv100-smp",
			     &hi3798mv100_smp_ops);
