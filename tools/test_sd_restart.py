#!/usr/bin/env python3
"""Execute the actual SD-profile restart probe without arming any watchdog."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define __iomem
#define ENODEV 19
#define EINVAL 22
#define ENOMEM 12
#define EIO 5
#define IORESOURCE_MEM 1
#define GFP_KERNEL 0
#define SYS_OFF_MODE_RESTART 1
#define SYS_OFF_PRIO_DEFAULT 0
#define IS_ERR(x) ((intptr_t)(x) == -EIO)
#define PTR_ERR(x) (-EIO)
struct device { int unused; };
struct platform_device { struct device dev; };
struct resource { uint64_t start, end; };
struct ty1208z_sd_restart_context { void *base, *sysid; };
struct sys_off_data { void *cb_data; };
static struct resource resources[3];
static struct ty1208z_sd_restart_context context;
static unsigned maps, checked, registrations;
static int missing, map_failure, allocation, registration_error;
static bool board, extra, ready;
static char sysid, watchdog;
static unsigned callback_calls, delays;
#define NOTIFY_DONE 0
#define pr_err(...) ((void)0)
static void mdelay(unsigned ms) { assert(ms == 1000); delays++; }
static bool ty1208z_mv100_restart(void *base, void *id)
{ assert(base == &watchdog && id == &sysid); callback_calls++; return ready; }
static bool of_machine_is_compatible(const char *name)
{ assert(!strcmp(name, "tianyi,ty1208z-ca-sd-ident-ram")); return board; }
static struct resource *platform_get_resource(struct platform_device *p, int type, unsigned i)
{ assert(p && type == IORESOURCE_MEM && i < 3); return (int)i == missing || (i == 2 && !extra) ? NULL : &resources[i]; }
static uint64_t resource_size(struct resource *r) { return r->end - r->start + 1; }
static void *devm_kzalloc(struct device *d, unsigned size, int flag)
{ assert(d && size == sizeof(context) && flag == GFP_KERNEL); return allocation ? NULL : &context; }
static void *devm_platform_ioremap_resource(struct platform_device *p, unsigned i)
{ assert(p && maps++ < 2 && i == (maps == 1 ? 1U : 0U)); return (int)i == map_failure ? (void *)(intptr_t)-EIO : i ? (void *)&sysid : &watchdog; }
static bool ty1208z_mv100_restart_ready(void *base, void *id)
{ assert(base == &watchdog && id == &sysid && maps == 2); checked++; return ready; }
static int dev_err_probe(struct device *d, int error, const char *msg)
{ assert(d && msg); return error; }
static void dev_info(struct device *d, const char *msg) { assert(d && msg); }
static int devm_register_sys_off_handler(struct device *d, int mode, int priority, int (*callback)(struct sys_off_data *), void *ctx)
{ assert(d && mode == SYS_OFF_MODE_RESTART && priority == SYS_OFF_PRIO_DEFAULT && callback && ctx == &context && checked == 1); registrations++; return registration_error; }
static void initialize(void)
{
    resources[0] = (struct resource){0xf8a2c000, 0xf8a2cfff};
    resources[1] = (struct resource){0xf8000ee0, 0xf8000ee3};
    maps = checked = registrations = 0; missing = map_failure = -1;
    allocation = registration_error = 0; board = ready = true; extra = false;
}
'''
MAIN = r'''
int main(void)
{
    struct platform_device p = {0};
    initialize(); board = false;
    assert(ty1208z_sd_restart_probe(&p) == -ENODEV && !maps && !registrations);
    for (int i = 0; i < 2; i++) {
        initialize(); missing = i;
        assert(ty1208z_sd_restart_probe(&p) == -EINVAL && !maps);
        initialize(); resources[i].start++;
        assert(ty1208z_sd_restart_probe(&p) == -EINVAL && !maps);
        initialize(); resources[i].end++;
        assert(ty1208z_sd_restart_probe(&p) == -EINVAL && !maps);
        initialize(); map_failure = i;
        assert(ty1208z_sd_restart_probe(&p) == -EIO && !checked && !registrations);
    }
    initialize(); extra = true;
    assert(ty1208z_sd_restart_probe(&p) == -EINVAL && !maps);
    initialize(); allocation = 1;
    assert(ty1208z_sd_restart_probe(&p) == -ENOMEM && !maps);
    initialize(); ready = false;
    assert(ty1208z_sd_restart_probe(&p) == -ENODEV && checked == 1 && !registrations);
    initialize(); registration_error = -EIO;
    assert(ty1208z_sd_restart_probe(&p) == -EIO && registrations == 1);
    initialize(); assert(!ty1208z_sd_restart_probe(&p) && registrations == 1);
    struct sys_off_data data = {.cb_data = &context};
    ready = false; assert(!ty1208z_sd_restart_callback(&data) && callback_calls == 1 && !delays);
    ready = true; assert(!ty1208z_sd_restart_callback(&data) && callback_calls == 2 && delays == 1);
    puts("SD_RESTART_PROBE_PASS: exact board/resources, map/state denial and managed handler registration; no reset sent");
}
'''


def test():
    source = (ROOT / "overlay/drivers/power/reset/ty1208z-mv100-sd-restart.c").read_text()
    start = source.index("static int ty1208z_sd_restart_probe(")
    callback_start = source.index("static int ty1208z_sd_restart_callback(")
    function = source[callback_start:source.index("static const struct of_device_id", start)]
    with tempfile.TemporaryDirectory(prefix="sd-restart-") as directory:
        path = Path(directory)
        (path / "test.c").write_text(HARNESS + function + MAIN)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(path / "test.c"), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    test()
