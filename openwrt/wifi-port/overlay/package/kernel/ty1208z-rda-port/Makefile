# SPDX-License-Identifier: GPL-2.0-only
include $(TOPDIR)/rules.mk
include $(INCLUDE_DIR)/kernel.mk

PKG_NAME:=ty1208z-rda-port
PKG_VERSION:=1
PKG_RELEASE:=1
PKG_LICENSE:=ISC GPL-2.0-only
PKG_BUILD_PARALLEL:=1
PKG_FLAGS:=nonshared
PKG_FILE_DEPENDS:=$(TOPDIR)/ty1208z-rda-inputs

include $(INCLUDE_DIR)/package.mk

define KernelPackage/ty1208z-rda-port
  SUBMENU:=Wireless Drivers
  TITLE:=TY1208Z RDA USB port (hardware untested)
  DEPENDS:=@TARGET_hi3798mv100
  KCONFIG:=CONFIG_CFG80211=y CONFIG_USB=y CONFIG_FW_LOADER=y
  FILES:=$(PKG_BUILD_DIR)/rdawlan/rdawfmac.ko
endef

define KernelPackage/ty1208z-rda-port/description
 Separate compile experiment against native OpenWrt Linux 6.12 cfg80211/USB.
 No firmware or automatic module loading. Actual chip/USB/firmware startup
 and wireless operation remain unverified; named-iovar initialization is blocked.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) $(TOPDIR)/ty1208z-rda-inputs/source/. $(PKG_BUILD_DIR)/
	$(call Build/Patch)
	$(CP) $(TOPDIR)/ty1208z-rda-inputs/Kbuild $(PKG_BUILD_DIR)/rdawlan/Kbuild
endef

define Build/Compile
	+$(KERNEL_MAKE) M="$(PKG_BUILD_DIR)/rdawlan" modules
endef

$(eval $(call KernelPackage,ty1208z-rda-port))
