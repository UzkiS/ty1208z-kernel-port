#!/usr/bin/env python3
"""Generate a checked Linux 6.12 USB API patch; no module or hardware access."""
import argparse
import difflib
from pathlib import Path

from fetch_wifi import load_lock, verify


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Upstream USB anchor changed: {old!r}")
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Unmodified, locked RDA source directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    name = "rdawlan/wland_usb.c"
    item = next(item for item in load_lock()["files"] if item["path"] == name)
    data = (args.source / name).read_bytes()
    verify(item, data)
    original = data.decode("utf-8")
    patched = replace_once(original,
                           "static void wland_ops_usb_shutdown(struct device *dev);",
                           "static void wland_ops_usb_shutdown(struct usb_interface *intf);")
    patched = replace_once(patched,
                           "\t.drvwrap = {\n\t\t.driver = {\n\t\t\t.shutdown = &wland_ops_usb_shutdown,\n\t\t},\n\t},",
                           "\t.shutdown = wland_ops_usb_shutdown,")
    patched = replace_once(patched, """static void wland_ops_usb_shutdown(struct device *dev)
{
	struct device_driver *drv = &wland_usbdrvr.drvwrap.driver;
	int ret;

	WLAND_DBG(USB, INFO, "Enter\\n");

	ret = driver_for_each_device(drv, NULL, NULL, wland_usb_reset_device);
}""", """static void wland_ops_usb_shutdown(struct usb_interface *intf)
{
	/* USB core shuts down each interface; do not iterate unrelated devices. */
	wland_usb_reset_device(&intf->dev, NULL);
}""")
    patched = replace_once(patched, "\tstruct device_driver *drv = &wland_usbdrvr.drvwrap.driver;",
                           "\tstruct device_driver *drv = &wland_usbdrvr.driver;")
    result = "".join(difflib.unified_diff(original.splitlines(keepends=True),
                                         patched.splitlines(keepends=True),
                                         fromfile=f"a/{name}", tofile=f"b/{name}"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8", newline="\n")
    print("Generated checked USB shutdown API patch; other driver APIs remain unaudited")


if __name__ == "__main__":
    main()
