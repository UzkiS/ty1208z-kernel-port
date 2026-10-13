# TY1208Z SP805 system restart experiment

The native router now has a physically accepted, explicitly RAM-loaded restart
module: a graceful `reboot` reaches the CA loader, the UART tool stops and inspects
that fresh boot, and the exact router is transferred/CRC-checked and restored
without another power cycle. See [physical acceptance](../verification/native-restart-board-20261013.md).
Independent diagnostic profiles require matching restart and peripheral shutdown
integration before unattended image switching.
The later independent SD metadata profile now also carries the same measured
MV100 helper and passes explicit command reboot, read-back-checked SD shutdown
and automatic return to the native router; [SD board report](../verification/sd-ident-board-20261013.md).
`make restart` retains the original isolated SP805-ID candidate described below.

## Native router module and measured MV100 identity

Physical WDG0 ID cells return zero on this board. The original Hinas/SDK DT
uses `arm,primecell-periphid` to supply the SP805 ID; successful old-driver
registration is not a measurement of those ID cells. The original strict-ID
candidate remains hardware unaccepted and its guard is unchanged.

The module variant additionally maps only the already measured SYSID0 at
`0xf8000ee0`. It requires SYSID0 `0x37980100`, zero ID cells, disabled CONTROL,
LOAD/VALUE `0xffffffff`, and RIS/MIS/LOCK zero, exactly as observed physically.
Probe makes no control writes. The callback checks these conditions again before
the same four unlock/control/load/reset writes and flush. No clock, card or
security-state writes are needed. This variant is explicitly restricted to the
native RAM-router board identity; it does not broaden the ordinary diagnostic.

`tools/build_openwrt_restart_module.py` accepts the completed native router source,
native taskbase and delivered router artifacts. It checks the actual config,
zImage, symbols, native compiler/libc identity, ARM module ELF and vermagic before
export. It never loads the module. Build with the actual compiler; the separate
userspace wrapper's libc include flags are unsuitable for kernel modules.

`tools/board_restart_cli.py --port COM9 --profile router` owns the UART throughout
graceful OpenWrt shutdown and the next loader inspection. It checks the exact
kernel, official source revision, live DT, bound module and measured registration
first. Physical failure is never inferred as success or retried automatically.
The module is temporary and must be loaded after a fresh RAM boot. Persistent
installation and integration with other peripheral shutdown paths remain pending.

The Hinas runtime FDT identifies an SP805 at `0xf8a2c000`, size `0x1000`, and
its boot log reports successful `sp805-wdt` registration. Pinned SDK
`arch/arm/mach-hi3798mx/core.c` binds `hi3798mv100-series` and restarts through
WDG0 unlock/load/control; the pinned `platform.h` gives the same address.
These sources are recorded in `reference/reference-manifest.json`. The
mainline Linux 6.12 SP805 restart handler confirms the register protocol.
The candidate does not copy the SDK watchdog code or its unrelated MMC quirk.

## Operation and boundaries

The dedicated platform driver reads the real AMBA peripheral/cell IDs and
CONTROL, requiring SP805 peripheral ID `0x00141805` under the upstream
24-bit mask, cell ID `0xb105f00d` and disabled CONTROL `0`. It does not rely on
a DT ID override. Probe and handler registration have no control writes.
An unexpected identity or active watchdog prevents registration.

Only an explicit kernel restart invokes the callback. The callback checks
the identity/control again before four writes: unlock, disabled control,
short load `0x100`, then interrupt/reset control `3`, followed by a posted-write
flush. A failed check performs no writes. Failure to reset is reported after
a bounded wait; hardware reboot is not inferred from issuing the command.

This is restart support only, not a watchdog service. WATCHDOG, storage, USB,
network, modules, SMP and debugfs are disabled. The exact DT contains only
the base UART/timer/memory and one restart controller. ARCH_HISI still
selects its generic reset driver; this profile contains no node it can bind.
The profile rejects additional reset drivers and controller resources.

## Validation and UART workflow

[Offline acceptance](../verification/restart-offline-20261012.md) records
the actual candidate identity, build, helper sanitizer, DT/config/layout,
serial PTY and generic QEMU results. No physical reboot has been tested.

After a separately validated RAM boot, capture registration without reset:

```text
python tools/board_diag_cli.py --port COM9 --profile restart1
```

For the authorized physical restart experiment, use the exclusive-port CLI:

```text
python tools/board_restart_cli.py --port COM9
```

It requires the exact `restart1` kernel and actual registration output,
issues one fixed `reboot -f` because PID 1 is the RAM diagnostic shell, then
identifies and interrupts the fresh CA boot and performs only fixed read-only
bootloader queries. It records TX/RX and a digest, rejects foreign systems,
missing/echoed acceptance markers and failed reset, and never retries reset.
No storage or persistent environment command is sent. Do not open a separate
boot listener or HiTool while this tool owns the port.

Successful physical restart would permit subsequent experiments to switch
images without a power cycle. Full storage/network/Wi-Fi integration still
needs appropriate driver shutdown and renewed restart acceptance; this
storage-disabled result cannot establish those future behaviors.
