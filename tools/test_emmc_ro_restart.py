#!/usr/bin/env python3
"""Execute the actual reset probe/callback with no physical reset writes."""
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
#define NOTIFY_DONE 0
#define pr_err(...) ((void)0)
#define BIT(n) (1U << (n))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
static bool native_mode;
#define CONFIG_TY1208Z_ROUTER_EMMC_RO native_mode
#define IS_ENABLED(x) (x)
typedef uint64_t resource_size_t;
struct device { int unused; };
struct platform_device { struct device dev; };
struct resource { uint64_t start, end; };
struct ty1208z_emmc_ro_restart_context { void *base, *sysid, *controller, *crg; };
struct sys_off_data { void *cb_data; };
static struct resource resources[5];
static struct ty1208z_emmc_ro_restart_context context;
static unsigned maps, registrations, restart_calls, delays;
static int missing, map_failure, allocation, registration_error;
static bool board, extra, ready;
static const char *board_name;
static char sysid, watchdog;
static uint32_t crg, controller[1024];
static uint32_t readl(void *address) { return *(uint32_t *)address; }
static void mdelay(unsigned ms) { assert(ms == 1000); delays++; }
static bool ty1208z_mv100_restart(void *base, void *id)
{ assert(base == &watchdog && id == &sysid); restart_calls++; return ready; }
static bool of_machine_is_compatible(const char *name)
{ return board && !strcmp(name, board_name); }
static struct resource *platform_get_resource(struct platform_device *p, int type, unsigned i)
{ assert(p && type == IORESOURCE_MEM && i < 5); return (int)i == missing || (i == 4 && !extra) ? NULL : &resources[i]; }
static uint64_t resource_size(struct resource *r) { return r->end - r->start + 1; }
static void *devm_kzalloc(struct device *d, unsigned size, int flag)
{ assert(d && size == sizeof(context) && flag == GFP_KERNEL); return allocation ? NULL : &context; }
static void *devm_platform_ioremap_resource(struct platform_device *p, unsigned i)
{
    const unsigned order[] = {1, 0};
    assert(p && maps < 2 && i == order[maps++]);
    if ((int)i == map_failure) return (void *)(intptr_t)-EIO;
    void *values[] = {&watchdog, &sysid, controller, &crg}; return values[i];
}
static void *devm_ioremap(struct device *d, uint64_t start, uint64_t size)
{
    unsigned i = maps == 2 ? 3 : 2;
    assert(d && maps >= 2 && maps < 4 && start == resources[i].start && size == resources[i].end - start + 1);
    maps++; return (int)i == map_failure ? NULL : i == 3 ? (void *)&crg : controller;
}
static bool ty1208z_mv100_restart_ready(void *base, void *id)
{ assert(base == &watchdog && id == &sysid && maps == 4); return ready; }
static int dev_err_probe(struct device *d, int error, const char *msg)
{ assert(d && msg); return error; }
static void dev_info(struct device *d, const char *msg) { assert(d && msg); }
static int devm_register_sys_off_handler(struct device *d, int mode, int priority, int (*callback)(struct sys_off_data *), void *ctx)
{ assert(d && mode == SYS_OFF_MODE_RESTART && priority == SYS_OFF_PRIO_DEFAULT && callback && ctx == &context); registrations++; return registration_error; }
static void initialize(void)
{
    resources[0] = (struct resource){0xf8a2c000, 0xf8a2cfff};
    resources[1] = (struct resource){0xf8000ee0, 0xf8000ee3};
    resources[2] = (struct resource){0xf9830000, 0xf9830fff};
    resources[3] = (struct resource){0xf8a220a0, 0xf8a220a3};
    maps = registrations = restart_calls = delays = 0; missing = map_failure = -1;
    allocation = registration_error = 0; board = ready = true; extra = false;
    board_name = "tianyi,ty1208z-ca-emmc-ro-ram";
    crg = 0x40103; memset(controller, 0, sizeof(controller));
    controller[0x6c / 4] = 0x5342270a; controller[0x70 / 4] = 0x00e44c81;
}
/* ACTUAL */
int main(void)
{
    struct platform_device p = {0};
    const char *identities[] = {"tianyi,ty1208z-ca-emmc-ro-ram", "tianyi,ty1208z-ca-openwrt-emmcro-ram", "foreign"};
    for (unsigned selected = 0; selected < 2; selected++) {
        native_mode = selected;
        for (unsigned i = 0; i < 3; i++) {
            initialize(); board_name = identities[i];
            bool accepted = i == 0 || (i == 1 && selected);
            assert(ty1208z_emmc_ro_restart_probe(&p) == (accepted ? 0 : -ENODEV));
            assert(registrations == (unsigned)accepted);
            if (!accepted) assert(!maps);
            assert(!restart_calls);
        }
    }
    native_mode = false;
    initialize(); board = false;
    assert(ty1208z_emmc_ro_restart_probe(&p) == -ENODEV && !maps && !registrations);
    for (int i = 0; i < 4; i++) {
        initialize(); missing = i;
        assert(ty1208z_emmc_ro_restart_probe(&p) == -EINVAL && !maps);
        initialize(); resources[i].start++;
        assert(ty1208z_emmc_ro_restart_probe(&p) == -EINVAL && !maps);
        initialize(); resources[i].end++;
        assert(ty1208z_emmc_ro_restart_probe(&p) == -EINVAL && !maps);
        initialize(); map_failure = i;
        assert(ty1208z_emmc_ro_restart_probe(&p) == (i < 2 ? -EIO : -ENOMEM) && !registrations);
    }
    initialize(); extra = true; assert(ty1208z_emmc_ro_restart_probe(&p) == -EINVAL && !maps);
    initialize(); allocation = 1; assert(ty1208z_emmc_ro_restart_probe(&p) == -ENOMEM && !maps);
    initialize(); ready = false; assert(ty1208z_emmc_ro_restart_probe(&p) == -ENODEV && !registrations);
    initialize(); registration_error = -EIO;
    assert(ty1208z_emmc_ro_restart_probe(&p) == -EIO && registrations == 1);
    initialize(); controller[0x10 / 4] = 1; controller[0x24 / 4] = 7;
    assert(!ty1208z_emmc_ro_restart_probe(&p) && registrations == 1 && !restart_calls);
    struct sys_off_data data = {.cb_data = &context};
    assert(!ty1208z_emmc_ro_restart_callback(&data) && !restart_calls && !delays);
    controller[0x10 / 4] = controller[0x24 / 4] = 0;
    for (unsigned bit = 0; bit < 32; bit++) {
        uint32_t *identities[] = {&crg, &controller[0x6c / 4], &controller[0x70 / 4]};
        for (unsigned i = 0; i < 3; i++) {
            *identities[i] ^= 1U << bit;
            assert(!ty1208z_emmc_ro_restart_callback(&data) && !restart_calls);
            *identities[i] ^= 1U << bit;
        }
        const unsigned offsets[] = {0x24, 0x10, 0x90};
        for (unsigned i = 0; i < 3; i++) {
            controller[offsets[i] / 4] = 1U << bit;
            assert(!ty1208z_emmc_ro_restart_callback(&data) && !restart_calls);
            controller[offsets[i] / 4] = 0;
        }
    }
    controller[0] = BIT(5); assert(!ty1208z_emmc_ro_restart_callback(&data) && !restart_calls);
    controller[0] = BIT(25); assert(!ty1208z_emmc_ro_restart_callback(&data) && !restart_calls);
    controller[0] = 0;
    ready = false; assert(!ty1208z_emmc_ro_restart_callback(&data) && restart_calls == 1 && !delays);
    ready = true; assert(!ty1208z_emmc_ro_restart_callback(&data) && restart_calls == 2 && delays == 1);
    puts("EMMC_RO_RESTART_PASS: actual resource/identity probe and callback, every controller quiescence/identity failure denies reset dispatch; no physical reset");
}
'''


def test():
    source = (ROOT / 'overlay/drivers/power/reset/ty1208z-mv100-emmc-ro-restart.c').read_text()
    functions = source[source.index('static bool ty1208z_emmc_ro_identity('):source.index('static const struct of_device_id')]
    with tempfile.TemporaryDirectory(prefix='emmc-ro-restart-') as directory:
        path = Path(directory)
        (path / 'test.c').write_text(HARNESS.replace('/* ACTUAL */', functions))
        binary = path / 'test'
        subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie', str(path / 'test.c'),
                        '-o', str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == '__main__':
    test()
