#!/usr/bin/env python3
"""Execute the real RAM-module registration and unwind paths under sanitizers."""
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
#define __init
#ifndef CONFIG_TY1208Z_ROUTER_RAM768
#define CONFIG_TY1208Z_ROUTER_RAM768 0
#endif
#define IS_ENABLED(x) (x)
#define __exit
#define ENODEV 19
#define EIO 5
#define IORESOURCE_MEM 0x200
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define IS_ERR(x) ((intptr_t)(x) < 0)
#define PTR_ERR(x) ((int)(intptr_t)(x))
struct resource { uint64_t start, end; unsigned long flags; };
struct platform_device { int bound; };
static struct platform_device device, *ty1208z_restart_device;
static int ty1208z_restart_driver;
static const char *board;
static unsigned mode, events;
static bool of_machine_is_compatible(const char *name)
{ return !strcmp(name, board); }
static int platform_driver_register(void *driver)
{ assert(driver == &ty1208z_restart_driver && events++ == 0); return mode == 1 ? -EIO : 0; }
static struct platform_device *platform_device_register_simple(
    const char *name, int id, const struct resource *res, unsigned count)
{
    assert(events++ == 1 && !strcmp(name, "ty1208z-sp805-restart") && id == -1);
    assert(count == 2 && res[0].start == 0xf8a2c000 && res[0].end == 0xf8a2cfff);
    assert(res[1].start == 0xf8000ee0 && res[1].end == 0xf8000ee3);
    assert(res[0].flags == IORESOURCE_MEM && res[1].flags == IORESOURCE_MEM);
    device.bound = mode != 3;
    return mode == 2 ? (void *)(intptr_t)-EIO : &device;
}
static void *platform_get_drvdata(struct platform_device *dev)
{ assert(dev == &device && events == 2); return device.bound ? &device : NULL; }
static void platform_device_unregister(struct platform_device *dev)
{ assert(dev == &device && events++ == 2); }
static void platform_driver_unregister(void *driver)
{ assert(driver == &ty1208z_restart_driver && events++ == (mode == 2 ? 2U : 3U)); }
'''
MAIN = r'''
int main(void)
{
    board = "other,board";
    assert(ty1208z_ram_restart_init() == -ENODEV && !events);
    board = "tianyi,ty1208z-ca-openwrt-router768-ram";
#if CONFIG_TY1208Z_ROUTER_RAM768
    mode = events = 0;
    assert(ty1208z_ram_restart_init() == 0 && events == 2);
    ty1208z_ram_restart_exit();
#else
    assert(ty1208z_ram_restart_init() == -ENODEV && !events);
#endif
    events = 0;
    board = "tianyi,ty1208z-ca-openwrt-router-ram";
    for (mode = 1; mode <= 3; mode++) {
        events = 0;
        assert(ty1208z_ram_restart_init() == (mode == 3 ? -ENODEV : -EIO));
        const unsigned expected[] = {0, 1, 3, 4};
        assert(events == expected[mode]);
    }
    mode = events = 0;
    assert(ty1208z_ram_restart_init() == 0 && events == 2);
    ty1208z_ram_restart_exit();
    assert(events == 4);
    puts("SP805_RAM_MODULE_LIFECYCLE_PASS: board gate, failed registration/probe unwind, managed removal");
}
'''


def test():
    source = (ROOT / "overlay/drivers/power/reset/ty1208z-sp805-restart.c").read_text()
    start = source.index("static int __init ty1208z_ram_restart_init(void)")
    end = source.index("module_init(ty1208z_ram_restart_init);", start)
    exit_start = source.index("static void __exit ty1208z_ram_restart_exit(void)", end)
    exit_end = source.index("module_exit(ty1208z_ram_restart_exit);", exit_start)
    with tempfile.TemporaryDirectory(prefix="restart-module-") as directory:
        path = Path(directory)
        program = path / "test.c"
        program.write_text(HARNESS + source[start:end] + source[exit_start:exit_end] + MAIN)
        binary = path / "test"
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        str(program), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)
        subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
                        "-DCONFIG_TY1208Z_ROUTER_RAM768=1", str(program), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == "__main__":
    test()
