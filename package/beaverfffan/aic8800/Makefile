# SPDX-License-Identifier: GPL-2.0-only
#
# Copyright (c) 2025 ImmortalWrt.org

include $(TOPDIR)/rules.mk

PKG_NAME:=aic8800
PKG_RELEASE:=5

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/radxa-pkg/aic8800.git
PKG_SOURCE_DATE:=2026-03-10
PKG_SOURCE_VERSION:=89f865b80f5f2ba6c0711c560e1d0191e87a1bf0
PKG_MIRROR_HASH:=fb54d2ac13109cf49c1b981424f26e3cc595826f033392284f6b3835a162e069

PKG_CONFIG_DEPENDS:=CONFIG_AIC8800_SDIO_BT_SUPPORT
PKG_FLAGS:=nonshared

include $(INCLUDE_DIR)/kernel.mk
include $(INCLUDE_DIR)/package.mk

define Package/aic8800-firmware/Default
  SECTION:=firmware
  CATEGORY:=Firmware
  TITLE:=Aicsemi aic8800 $(1) firmware
endef

Package/aic8800-pcie-firmware = $(call Package/aic8800-firmware/Default,PCIe)
Package/aic8800-sdio-firmware = $(call Package/aic8800-firmware/Default,SDIO)
Package/aic8800-usb-firmware = $(call Package/aic8800-firmware/Default,USB)

define KernelPackage/aic8800/Default
  SUBMENU:=Wireless Drivers
  TITLE:=Aicsemi aic8800 Wi-Fi $(1) support
  DEPENDS:=+kmod-cfg80211 +@DRIVER_11N_SUPPORT +@DRIVER_11AC_SUPPORT \
    +@DRIVER_11AX_SUPPORT
endef

define KernelPackage/aic8800-btusb
  SUBMENU:=Bluetooth Support
  TITLE:=Aicsemi aic8800 Bluetooth USB support
  DEPENDS:=+aic8800-usb-firmware +kmod-usb-core +kmod-bluetooth
  FILES:=$(PKG_BUILD_DIR)/src/USB/driver_fw/drivers/aic_btusb/aic_btusb.ko
  AUTOLOAD:=$(call AutoProbe,aic_btusb)
endef

define KernelPackage/aic8800-pcie
  $(call KernelPackage/aic8800/Default,PCIe)
  DEPENDS+= +aic8800-pcie-firmware @PCIE_SUPPORT
  FILES:=$(PKG_BUILD_DIR)/src/PCIE/driver_fw/driver/aic8800/aic8800_fdrv/aic8800D80_fdrv.ko
  AUTOLOAD:=$(call AutoProbe,aic8800D80_fdrv)
endef

define KernelPackage/aic8800-sdio
  $(call KernelPackage/aic8800/Default,SDIO)
  # ★ BT 相关的两个条件依赖（+AIC8800_SDIO_BT_SUPPORT:input-support /
  #   :kmod-bluetooth）在 x-wrt 26.10 上会让 kconfig 报
  #       PACKAGE_input-support is selected by PACKAGE_kmod-aic8800-sdio
  #       PACKAGE_kmod-aic8800-sdio depends on PACKAGE_input-support
  #   即「自己 select 自己 depends 的包」成环，`make defconfig` 直接报 error
  #   （immortalwrt 上不报，但 x-wrt 的 kconfig 版本更严）。
  #   ⇒ 只保留编译开关，不再自动拉 input-support / kmod-bluetooth；
  #     需要蓝牙的自己在 .config 里加 CONFIG_PACKAGE_kmod-bluetooth=y 即可。
  DEPENDS+= +aic8800-sdio-firmware +kmod-mmc
  FILES:= \
	$(PKG_BUILD_DIR)/src/SDIO/driver_fw/driver/aic8800/aic8800_bsp/aic8800_bsp.ko \
	$(PKG_BUILD_DIR)/src/SDIO/driver_fw/driver/aic8800/aic8800_fdrv/aic8800_fdrv.ko
  AUTOLOAD:=$(call AutoProbe,aic8800_bsp aic8800_fdrv)
endef

define KernelPackage/aic8800-sdio/config
	# ★ 也不能在外面套 `if PACKAGE_kmod-aic8800-sdio` / `endif`：
	#   那样符号会依赖 PACKAGE_kmod-aic8800-sdio，同样成环。
	# ★ 默认必须 **n**：打开了它驱动会引用 Bluetooth HCI 符号
	#   （hci_register_dev / hci_recv_frame / hci_unregister_dev），
	#   而我们上面为了避开 kconfig 成环已经把 kmod-bluetooth 的条件依赖去掉了
	#   ⇒ 内核没编 BT 时 modpost 直接失败：
	#       ERROR: modpost: "hci_register_dev" [aic8800_fdrv.ko] undefined!
	#   要用蓝牙就同时开：CONFIG_AIC8800_SDIO_BT_SUPPORT=y +
	#   CONFIG_PACKAGE_kmod-bluetooth=y（并接受 SDIO BT 的 input-support 依赖）。
	config AIC8800_SDIO_BT_SUPPORT
		bool "Enable Bluetooth support (needs kmod-bluetooth)"
		default n
endef

define KernelPackage/aic8800-usb
  $(call KernelPackage/aic8800/Default,USB)
  DEPENDS+= +aic8800-usb-firmware +kmod-usb-core
  FILES:= \
	$(PKG_BUILD_DIR)/src/USB/driver_fw/drivers/aic8800/aic_load_fw/aic_load_fw.ko \
	$(PKG_BUILD_DIR)/src/USB/driver_fw/drivers/aic8800/aic8800_fdrv/aic8800DC_fdrv.ko
  AUTOLOAD:=$(call AutoProbe,aic_load_fw aic8800DC_fdrv)
endef

NOSTDINC_FLAGS:= \
	$(KERNEL_NOSTDINC_FLAGS) \
	-I$(PKG_BUILD_DIR) \
	-I$(PKG_BUILD_DIR)/include \
	-I$(STAGING_DIR)/usr/include/mac80211-backport \
	-I$(STAGING_DIR)/usr/include/mac80211-backport/uapi \
	-I$(STAGING_DIR)/usr/include/mac80211 \
	-I$(STAGING_DIR)/usr/include/mac80211/uapi \
	-include backport/autoconf.h \
	-include backport/backport.h \
	-DBUILD_OPENWRT

define Build/Compile

ifneq ($(CONFIG_PACKAGE_kmod-aic8800-btusb),)
	+$(KERNEL_MAKE) $(PKG_JOBS) \
		M="$(PKG_BUILD_DIR)/src/USB/driver_fw/drivers/aic_btusb" \
		NOSTDINC_FLAGS="$(NOSTDINC_FLAGS)" \
		KCFLAGS="-Wno-error" \
		CONFIG_AIC_FW_PATH="/lib/firmware/aic8800/usb" \
		modules
endif
ifneq ($(CONFIG_PACKAGE_kmod-aic8800-sdio),)
	+$(KERNEL_MAKE) $(PKG_JOBS) \
		M="$(PKG_BUILD_DIR)/src/SDIO/driver_fw/driver/aic8800" \
		NOSTDINC_FLAGS="$(NOSTDINC_FLAGS)" \
		KCFLAGS="-Wno-error" \
		CONFIG_AIC_FW_PATH="/lib/firmware/aic8800/sdio" \
		CONFIG_AIC8800_BTLPM_SUPPORT=n \
		CONFIG_SDIO_BT=$(if $(CONFIG_AIC8800_SDIO_BT_SUPPORT),y,n) \
		modules
endif
ifneq ($(CONFIG_PACKAGE_kmod-aic8800-pcie),)
	+$(KERNEL_MAKE) $(PKG_JOBS) \
		M="$(PKG_BUILD_DIR)/src/PCIE/driver_fw/driver/aic8800/aic8800_fdrv" \
		NOSTDINC_FLAGS="$(NOSTDINC_FLAGS)" \
		KCFLAGS="-Wno-error" \
		CONFIG_AIC_FW_PATH="/lib/firmware/aic8800/pcie" \
		modules
endif
ifneq ($(CONFIG_PACKAGE_kmod-aic8800-usb),)
	+$(KERNEL_MAKE) $(PKG_JOBS) \
		M="$(PKG_BUILD_DIR)/src/USB/driver_fw/drivers/aic8800" \
		NOSTDINC_FLAGS="$(NOSTDINC_FLAGS)" \
		KCFLAGS="-Wno-error" \
		CONFIG_AIC_FW_PATH="/lib/firmware/aic8800/usb" \
		modules
endif
endef

define Package/aic8800-pcie-firmware/install
	$(INSTALL_DIR) $(1)/lib/firmware/aic8800/pcie
	$(CP) \
		$(PKG_BUILD_DIR)/src/PCIE/driver_fw/fw/aic8800D80/* \
		$(1)/lib/firmware/aic8800/pcie/
endef

define Package/aic8800-sdio-firmware/install
	$(INSTALL_DIR) $(1)/lib/firmware/aic8800/sdio
	$(CP) \
		$(PKG_BUILD_DIR)/src/SDIO/driver_fw/fw/aic8800/* \
		$(1)/lib/firmware/aic8800/sdio/
	$(CP) \
		$(PKG_BUILD_DIR)/src/SDIO/driver_fw/fw/aic8800D80/* \
		$(1)/lib/firmware/aic8800/sdio/
	$(CP) \
		$(PKG_BUILD_DIR)/src/SDIO/driver_fw/fw/aic8800D80N/* \
		$(1)/lib/firmware/aic8800/sdio/
	$(CP) \
		$(PKG_BUILD_DIR)/src/SDIO/driver_fw/fw/aic8800D80X2/* \
		$(1)/lib/firmware/aic8800/sdio/
	$(CP) \
		$(PKG_BUILD_DIR)/src/SDIO/driver_fw/fw/aic8800DC/* \
		$(1)/lib/firmware/aic8800/sdio/
endef

define Package/aic8800-usb-firmware/install
	$(INSTALL_DIR) $(1)/lib/firmware/aic8800/usb
	$(CP) \
		$(PKG_BUILD_DIR)/src/USB/driver_fw/fw/aic8800/* \
		$(1)/lib/firmware/aic8800/usb/
	$(CP) \
		$(PKG_BUILD_DIR)/src/USB/driver_fw/fw/aic8800D80/* \
		$(1)/lib/firmware/aic8800/usb/
	$(CP) \
		$(PKG_BUILD_DIR)/src/USB/driver_fw/fw/aic8800D80N/* \
		$(1)/lib/firmware/aic8800/usb/
	$(CP) \
		$(PKG_BUILD_DIR)/src/USB/driver_fw/fw/aic8800D80X2/* \
		$(1)/lib/firmware/aic8800/usb/
	$(CP) \
		$(PKG_BUILD_DIR)/src/USB/driver_fw/fw/aic8800DC/* \
		$(1)/lib/firmware/aic8800/usb/
	$(CP) \
		$(PKG_BUILD_DIR)/src/USB/driver_fw/fw/aic8800DLN/* \
		$(1)/lib/firmware/aic8800/usb/
endef

$(eval $(call BuildPackage,aic8800-pcie-firmware))
$(eval $(call BuildPackage,aic8800-sdio-firmware))
$(eval $(call BuildPackage,aic8800-usb-firmware))
$(eval $(call KernelPackage,aic8800-btusb))
$(eval $(call KernelPackage,aic8800-pcie))
$(eval $(call KernelPackage,aic8800-sdio))
$(eval $(call KernelPackage,aic8800-usb))
