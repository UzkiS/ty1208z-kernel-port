# SPDX-License-Identifier: GPL-2.0-only
# Package/rootfs generation only. The separate initrd and raw kernel are used
# by QEMU; this profile has no CA image or installation path for the board.
# Use the pinned upstream host compressor, as kernel-defaults.mk already does.
# This keeps both proxy cores within the 512-byte TFTP no-rollover boundary.
define Image/Build/cpiogz
	( cd $(TARGET_DIR); find . | LC_ALL=C sort | $(STAGING_DIR_HOST)/bin/cpio --reproducible -o -H newc -R 0:0 >$(KERNEL_BUILD_DIR)/ty1208z-rootfs.cpio )
	$(STAGING_DIR_HOST)/bin/libdeflate-gzip -12 -n -c $(KERNEL_BUILD_DIR)/ty1208z-rootfs.cpio >$(BIN_DIR)/$(IMG_ROOTFS).cpio.gz
endef

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
