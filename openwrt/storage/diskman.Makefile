include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-diskman
PKG_VERSION:=0.2.13
PKG_RELEASE:=3
PKG_LICENSE:=AGPL-3.0
PKG_MAINTAINER:=lisaac <https://github.com/lisaac/luci-app-diskman>

LUCI_TITLE:=Disk Manager for SD and USB storage
LUCI_DEPENDS:=+luci-compat +block-mount +lsblk +e2fsprogs +parted +smartmontools +blkid +dosfstools +exfat-mkfs +exfat-fsck

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt package scanner signature; luci.mk emits the call.
