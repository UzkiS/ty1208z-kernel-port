# SPDX-License-Identifier: MIT
include $(TOPDIR)/rules.mk

PKG_NAME:=ty1208z-time64
PKG_RELEASE:=1
PKG_LICENSE:=MIT

include $(INCLUDE_DIR)/package.mk

define Package/ty1208z-time64
	SECTION:=utils
	CATEGORY:=Utilities
	TITLE:=TY1208Z libc and RAM-file time64 diagnostic
endef

define Build/Prepare
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	$(CP) ./src/time64-probe.c $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CPPFLAGS) $(TARGET_CFLAGS) -Wall -Wextra -Werror \
		-o $(PKG_BUILD_DIR)/time64-probe $(PKG_BUILD_DIR)/time64-probe.c $(TARGET_LDFLAGS)
endef

define Package/ty1208z-time64/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/time64-probe $(1)/usr/bin/time64-probe
endef

$(eval $(call BuildPackage,ty1208z-time64))
