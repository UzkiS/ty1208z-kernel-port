# SPDX-License-Identifier: GPL-2.0-only
define Device/ty1208z_ca_net
	DEVICE_VENDOR := Tianyi
	DEVICE_MODEL := TY1208Z CA
	DEVICE_VARIANT := inherited-PHY RAM UNTESTED
	DEVICE_PACKAGES := ty1208z-time64 iperf3
	DEVICE_DTS := hi3798mv100-ty1208z-openwrt-net
	DTS_DIR := $(DTS_DIR)/hisilicon
	KERNEL_NAME := zImage
	KERNEL_LOADADDR := 0x02000000
	KERNEL_ENTRY := 0x02000000
	KERNEL_SUFFIX := -uImage-UNTESTED.bin
	KERNEL_INITRAMFS := kernel-bin | append-dtb | uImage none
	KERNEL_INSTALL :=
	IMAGES :=
endef
TARGET_DEVICES += ty1208z_ca_net

$(eval $(call BuildImage))
