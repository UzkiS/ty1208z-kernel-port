-- SPDX-License-Identifier: AGPL-3.0-only
-- Board policy for DiskMan. The installed eMMC belongs to the upgrade backend.
local fs = require "nixio.fs"
local policy = {}

function policy.allowed_disk(name)
    if type(name) ~= "string" then return false end
    if name == "mmcblk1" then
        return (fs.readfile("/sys/class/block/mmcblk1/device/type") or ""):match("^SD%s*$") ~= nil
    end
    if name:match("^sd[a-z]+$") then
        local path = fs.realpath("/sys/class/block/" .. name) or ""
        return path:match("/usb%d+/") ~= nil
    end
    return false
end

function policy.parent(name)
    if type(name) ~= "string" then return nil end
    if policy.allowed_disk(name) then return name end
    local disk = name:match("^(mmcblk1)p[1-9]%d*$") or name:match("^(sd[a-z]+)[1-9]%d*$")
    if disk and policy.allowed_disk(disk) and fs.access("/sys/class/block/" .. name .. "/partition") then
        local parent = fs.realpath("/sys/class/block/" .. disk) or ""
        if fs.realpath("/sys/class/block/" .. name) == parent .. "/" .. name then return disk end
    end
    return nil
end

function policy.idle(name)
    local disk = policy.parent(name)
    if not disk then return false, "Only SD and USB data disks can be changed." end
    local mounts = fs.readfile("/proc/self/mountinfo")
    local swaps = fs.readfile("/proc/swaps")
    if not mounts or not swaps then return false, "Cannot inspect active mounts and swap." end
    local function active(part)
        local dev = (fs.readfile("/sys/class/block/" .. part .. "/dev") or ""):match("^(%d+:%d+)")
        if not dev then return true end
        for line in mounts:gmatch("[^\n]+") do
            if line:match("^%d+ %d+ " .. dev .. " ") then return true end
        end
        if swaps:match("\n/dev/" .. part .. "%s") then return true end
        local holders = fs.dir("/sys/class/block/" .. part .. "/holders")
        if holders then
            for entry in holders do
                if entry ~= "." and entry ~= ".." then return true end
            end
        else return true end
        return false
    end
    if not (fs.readfile("/sys/class/block/" .. name .. "/ro") or ""):match("^0%s*$") then
        return false, "The device is read-only."
    end
    if active(name) then return false, "Please unmount the device and disable swap first." end
    if name == disk then
        for path in fs.glob("/sys/class/block/" .. disk .. "/" .. disk .. "*") do
            local part = fs.basename(path)
            if fs.access(path .. "/partition") and active(part) then
                return false, "Please unmount all partitions and disable swap first."
            end
        end
    end
    return true
end

return policy
