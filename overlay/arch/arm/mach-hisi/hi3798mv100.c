// SPDX-License-Identifier: GPL-2.0-only
/* Minimal UP diagnostic support; no vendor SMP, storage or security writes. */
#include <asm/mach/arch.h>
#include <asm/mach/map.h>

static const char *const hi3798mv100_compat[] __initconst = {
	"tianyi,ty1208z-ca-diagnostic",
	"hi3798mv100-series",
	NULL,
};

DT_MACHINE_START(HI3798MV100, "HiSilicon Hi3798MV100 diagnostic candidate")
	.atag_offset = 0x100,
	.map_io = debug_ll_io_init,
	.dt_compat = hi3798mv100_compat,
MACHINE_END
