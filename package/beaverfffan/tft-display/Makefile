#
# tft-display —— H29K 屏幕（GC9307 / ST7789V）上的 LVGL 系统信息页
#
# 上游：https://github.com/ouyangzq/H29KorH69K-OPENWRT  → tft-display/
#   （原项目名 luci-app-lvgl-sysinfo，作者 Fish <168620188@qq.com>）
#
# ★ 为什么不把源码 vendor 进来：src/ 有 **124 MB**（其中 lvgl 118 MB）。
#   两个适配层仓库各塞一份不合适 ⇒ 改成构建时从上游 git 拉（subdir=tft-display），
#   版本用 PKG_SOURCE_VERSION 钉死当前上游 HEAD。
#
# ★ 与上游 Makefile 的差异（都是本家这棵树的情况）：
#   1. 去掉 kmod-fb-tft-gc9307 / kmod-backlight-pwm / kmod-saradc-rockchip 三个
#      「自带内核模块」依赖 —— 本家把 fbtft + PWM 背光 + saradc 直接**内建**进
#      内核（见 hinlink-config.append），不需要外部 kmod 包。
#      （kmod-input-touchscreen-axs5106 也不在这里写：只有 1.49″ 触屏版需要，
#        由 DEVICE_PACKAGES 按机型加。）
#   2. 去掉 kmod-spi-bitbang / kmod-spi-dev —— 查过源码，程序只写 /dev/fb0，
#      不碰 spidev。
#   3. 加 luci-compat + luci-lua-runtime —— 它自带的配置页是 **Lua CBI**（luci 兼容层）。
#
include $(TOPDIR)/rules.mk

PKG_NAME:=tft-display
PKG_VERSION:=2.19
PKG_RELEASE:=1
PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/ouyangzq/H29KorH69K-OPENWRT.git
PKG_SOURCE_VERSION:=8910dc75db7169157565eb6556ba4b33d6489377
PKG_SOURCE_DATE:=2026-10-17
PKG_MIRROR_HASH:=skip

PKG_LICENSE:=GPL
PKG_MAINTAINER:=Fish <168620188@qq.com>（Beaverfffan 适配进 hinlink 树）
PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk

define Package/$(PKG_NAME)
  SECTION:=utils
  CATEGORY:=Utilities
  SUBMENU:=3. Applications
  TITLE:=LVGL system information display (H29K TFT)
  DEPENDS:=+luci-compat +luci-lua-runtime
endef

define Package/$(PKG_NAME)/description
 在 H29K 的 SPI 小屏（GC9307 1.49" / ST7789V 1.14"）上显示系统信息：
 CPU / 内存 / 网络 / 温度 / 电池，带息屏与亮度调节。
 基于 LVGL，写 /dev/fb0，背光走 /sys/class/backlight。
endef

# 源码在 clone 下来的 monorepo 的 tft-display/ 子目录里。
# ★ 本目录下的 `files/`（init.d / uci-defaults / config / 两个 lua）只是**参考副本**，
#   install 用的是源码树里的 `$(TFT_SRC)/files`。留一份是为了看清我们依赖哪些文件、
#   以及便于 diff（上游那几份是 CRLF，git 里必须保持 LF）。
TFT_SRC=$(PKG_BUILD_DIR)/tft-display

# ⚠️ CFLAGS / LDFLAGS 必须用**环境变量**方式传（`VAR=... $(MAKE)`）；
#   写成 `$(MAKE) ... CFLAGS=...` 会让 src/Makefile 里所有 `CFLAGS +=` 失效
#   （GNU make 的规定）—— lvgl 的 include 路径就是靠那些 += 加的。
# ⚠️ -Wno-error=...：这份代码是 GCC 13 时代的，我们这棵是 GCC 14，
#   后者把一批写法升格成硬错误。降回警告，保证与设备上已验证的行为一致。
TFT_WARN_NOWERROR=-Wno-error=incompatible-pointer-types \
	-Wno-error=implicit-function-declaration -Wno-error=implicit-int \
	-Wno-error=int-conversion -Wno-error=return-mismatch \
	-Wno-error=declaration-missing-parameter-type

define Build/Compile
	CC="$(TARGET_CC)" \
	CFLAGS="$(TARGET_CFLAGS) $(TFT_WARN_NOWERROR)" \
	LDFLAGS="$(TARGET_LDFLAGS) -lm" \
	TFT_VERSION="$(PKG_VERSION)-$(PKG_RELEASE)" \
	$(MAKE) -C $(TFT_SRC)/src
endef

define Package/$(PKG_NAME)/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(TFT_SRC)/src/tftdisplay $(1)/usr/bin/tftdisplay
	$(CP) $(TFT_SRC)/files/* $(1)/
	# 包内 init 脚本 / uci-defaults 必须可执行（Windows↔构建机往返会丢 exec 位）
	chmod 755 $(1)/etc/init.d/tftdisplay $(1)/etc/uci-defaults/90-tftdisplay-idle
endef

define Package/$(PKG_NAME)/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/tftdisplay enable
	/etc/init.d/tftdisplay restart
}
exit 0
endef

$(eval $(call BuildPackage,$(PKG_NAME)))
