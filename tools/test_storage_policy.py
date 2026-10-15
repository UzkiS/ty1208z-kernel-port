#!/usr/bin/env python3
"""Run the actual DiskMan board guard in packaged ARM Lua using synthetic sysfs."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LUA = r'''
local files, links, holders, children = {}, {}, {}, {}
local function iter(values)
    local n = 0
    return function() n = n + 1; return values[n] end
end
package.preload["nixio.fs"] = function()
    return {
        readfile = function(path) return files[path] end,
        access = function(path) return files[path] ~= nil end,
        realpath = function(path) return links[path] end,
        basename = function(path) return path:match("([^/]+)$") end,
        dir = function(path) return iter(holders[path] or {".", ".."}) end,
        glob = function() return iter(children) end
    }
end
local policy = dofile(arg[1])
local function setup()
    files, links, holders, children = {}, {}, {}, {}
    files["/proc/self/mountinfo"] = ""
    files["/proc/swaps"] = "Filename Type Size Used Priority\n"
    files["/sys/class/block/mmcblk1/device/type"] = "SD\n"
    for name, number in pairs({mmcblk1="179:32", mmcblk1p1="179:33", sda="8:0", sda1="8:1"}) do
        files["/sys/class/block/" .. name .. "/dev"] = number .. "\n"
        files["/sys/class/block/" .. name .. "/ro"] = "0\n"
    end
    files["/sys/class/block/mmcblk1p1/partition"] = "1\n"
    files["/sys/class/block/mmcblk1/mmcblk1p1/partition"] = "1\n"
    files["/sys/class/block/sda1/partition"] = "1\n"
    links["/sys/class/block/mmcblk1"] = "/devices/mmc/block/mmcblk1"
    links["/sys/class/block/mmcblk1p1"] = "/devices/mmc/block/mmcblk1/mmcblk1p1"
    links["/sys/class/block/sda"] = "/devices/usb1/1-1/block/sda"
    links["/sys/class/block/sda1"] = "/devices/usb1/1-1/block/sda/sda1"
    children = {"/sys/class/block/mmcblk1/mmcblk1p1"}
end
setup()
for _, name in ipairs({"mmcblk1", "mmcblk1p1", "sda", "sda1"}) do assert(policy.idle(name), name) end
for _, name in ipairs({"mmcblk0", "mmcblk0p6", "mmcblk0p9", "mmcblk0boot0", "mmcblk0rpmb",
                       "../sda", "sda;echo injected", "sda1\n", "mmcblk1p0", "loop0", "dm-0"}) do
    assert(not policy.idle(name), name)
end
files["/sys/class/block/mmcblk1/device/type"] = "MMC\n"
assert(not policy.idle("mmcblk1"))
setup()
links["/sys/class/block/sda"] = "/devices/platform/ata/block/sda"
assert(not policy.idle("sda"))
setup()
links["/sys/class/block/mmcblk1p1"] = "/devices/mmc/block/mmcblk0/mmcblk0p9"
assert(not policy.idle("mmcblk1p1"))
setup()
files["/sys/class/block/mmcblk1p1/ro"] = "1\n"
assert(not policy.idle("mmcblk1p1"))
setup()
files["/proc/self/mountinfo"] = "42 1 179:33 / /mnt rw - vfat /dev/alias rw\n"
assert(not policy.idle("mmcblk1p1"))
assert(not policy.idle("mmcblk1"))
setup()
files["/proc/swaps"] = "Filename Type Size Used Priority\n/dev/mmcblk1p1 partition 100 0 -2\n"
assert(not policy.idle("mmcblk1p1"))
assert(not policy.idle("mmcblk1"))
setup()
holders["/sys/class/block/sda1/holders"] = {".", "..", "dm-0"}
assert(not policy.idle("sda1"))
setup()
files["/proc/self/mountinfo"] = nil
assert(not policy.idle("sda1"))
setup()
files["/sys/class/block/sda1/ro"] = nil
assert(not policy.idle("sda1"))
print("STORAGE_POLICY_ARM_PASS SD/USB allowed; eMMC, aliases, mounted children, swap, holders and read-only rejected")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument('--root', type=Path, help='Packaged native system with ARM Lua')
    location.add_argument('--source', type=Path, help='Completed native OpenWrt source tree')
    args = parser.parse_args()
    root = args.root
    if root is None:
        candidates = list((args.source / 'build_dir').glob('target-*/root-hi3798mv100'))
        if len(candidates) != 1:
            raise ValueError('Native root is missing or ambiguous')
        root = candidates[0]
    with tempfile.TemporaryDirectory(prefix='storage-policy-') as directory:
        script = Path(directory) / 'test.lua'
        script.write_text(LUA)
        subprocess.run(['qemu-arm', '-L', str(root), str(root / 'usr/bin/lua'),
                        str(script), str(ROOT / 'openwrt/storage/ty1208z.lua')], check=True)


if __name__ == '__main__':
    main()
