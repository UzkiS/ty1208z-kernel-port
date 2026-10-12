# SPDX-License-Identifier: GPL-2.0-only
# Package/rootfs generation only. The separate initrd and raw kernel are used
# by QEMU; this profile has no CA image or installation path for the board.
define Device/ty1208z_apps
	DEVICE_VENDOR := Tianyi
	DEVICE_MODEL := TY1208Z application validation
	DEVICE_VARIANT := QEMU only
	DEVICE_PACKAGES := ty1208z-time64
	KERNEL_NAME := zImage
	KERNEL_INITRAMFS :=
	KERNEL_INSTALL :=
	IMAGES :=
endef
TARGET_DEVICES += ty1208z_apps

$(eval $(call BuildImage))
