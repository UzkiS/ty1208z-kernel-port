# SPDX-License-Identifier: GPL-2.0-only
include $(TOPDIR)/rules.mk

ARCH:=arm
BOARD:=hi3798mv100
BOARDNAME:=HiSilicon Hi3798MV100 RAM bring-up
SUBTARGETS:=ram
FEATURES:=fpu ramdisk
CPU_TYPE:=cortex-a7
CPU_SUBTYPE:=neon-vfpv4
DEVICE_TYPE:=basic
KERNEL_PATCHVER:=6.12

include $(INCLUDE_DIR)/target.mk

KERNELNAME:=zImage dtbs
DEFAULT_PACKAGES := $(filter-out mtd procd-ujail,$(DEFAULT_PACKAGES))

define Target/Description
	Native TY1208Z CA RAM-only bring-up using the existing CA fastboot.
	UART, CPU0 and timer only; storage, Ethernet and USB are not enabled.
endef

$(eval $(call BuildTarget))
