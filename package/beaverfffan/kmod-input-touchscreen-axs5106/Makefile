#
# AXS5106 / AXS5105 触摸屏驱动（自带源码的内核外模块，不改动 lede 原始代码）
#
# 源码 src/axs5106.c 取自 E:\OPENWRT\资料\DCR\Hinlink\5106\V2.patch
#   那份补丁原本是把该文件新增到内核树 drivers/input/touchscreen/ 并改 Kconfig/Makefile；
#   这里改成内核外编译，于是不再需要内核补丁，也不需要 KCONFIG。
#
include $(TOPDIR)/rules.mk
include $(INCLUDE_DIR)/kernel.mk

PKG_NAME:=kmod-input-touchscreen-axs5106
PKG_RELEASE:=1
# 注意：本目录/PKG_NAME 用完整包名 kmod-xxx（与生成的 ipk 同名，符合 OpenWrt 习惯）；
#       但下面 KernelPackage/input-touchscreen-axs5106 里不能带 kmod- 前缀。
#       因为 include/kernel.mk:271 是 $(eval $(call BuildPackage,kmod-$(1)))，
#       ipk 名由内核宏自动加 kmod-；若这里也写 kmod- 就会变成 kmod-kmod-xxx。
#       ipk 名不变 ⇒ tftdisplay 的 DEPENDS(+kmod-xxx) 与 .config 选择都不用改。
PKG_LICENSE:=GPL-2.0
PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk

# ---------------------------------------------------------------------------
# GCC 14（openwrt 工具链）把一批原本只是警告的写法升格成了硬错误：
#   -Wincompatible-pointer-types / -Wimplicit-function-declaration / -Wimplicit-int
#   / -Wint-conversion / -Wreturn-mismatch / -Wdeclaration-missing-parameter-type
# 这份代码是 GCC 13（lede）时代写的、真机上跑通了，这里把它们降回警告，
# 保证与设备上已验证的固件行为一致。
# ---------------------------------------------------------------------------
TARGET_CFLAGS += -Wno-error=incompatible-pointer-types -Wno-error=implicit-function-declaration -Wno-error=implicit-int -Wno-error=int-conversion -Wno-error=return-mismatch -Wno-error=declaration-missing-parameter-type

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./src/* $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(KERNEL_MAKE) M="$(PKG_BUILD_DIR)" modules
endef

define KernelPackage/input-touchscreen-axs5106
  SECTION:=kernel
  SUBMENU:=Input modules
  TITLE:=AXS5106 / AXS5105 I2C touchscreen (out-of-tree)
  DEPENDS:=+kmod-i2c-core +kmod-input-core
  FILES:=$(PKG_BUILD_DIR)/axs5106.ko
  AUTOLOAD:=$(call AutoProbe,axs5106)
endef

define KernelPackage/input-touchscreen-axs5106/description
  Kernel module for AXS5105, Evervision AXS5105 \
  and Focaltech AXS5105 based touchscreens.
  Built out-of-tree from src/axs5106.c.
endef

$(eval $(call KernelPackage,input-touchscreen-axs5106))
