#!/bin/sh
# ============================================================================
# 编译全部 16 个 HinLink 机型的固件
#
#   sh tools/build_all.sh            # 默认 -j$(nproc)
#   sh tools/build_all.sh -j8
#
# 在 immortalwrt 树根目录执行（需先跑过 tools/integrate.py）。
#
# ★ 关键点（踩过的坑，别改）：
#   1) 多机型必须用 TARGET_MULTI_PROFILE + TARGET_DEVICE_<board>_<sub>_DEVICE_<机型>
#      这一组符号；单选 choice 里的 TARGET_<board>_<sub>_DEVICE_<机型> 选了 16 个
#      也只有最后一个生效（kconfig 会报 "changes choice state"）。
#   2) 这两个开关必须写进 .config stub 再 make defconfig，不能先 defconfig 再开。
#   3) PER_DEVICE_ROOTFS 选 n：所有机型共用一份 rootfs（= 包并集），
#      编得快，且 profile 包在 .config 里是 =y（选 y 会变成 =m + 16 份 rootfs）。
#   4) armv8.mk.hinlink 不在 prepare-tmpinfo 的依赖里，改完必须清 tmp 缓存。
# ============================================================================
set -e

JOBS="$(nproc)"
[ "$1" = "-j" ] && JOBS="$2"

DEVICES="
hinlink_opc-h66k
hinlink_opc-h68k-a-b
hinlink_opc-h68k-a-b-usb
hinlink_opc-h68k-c-d-f
hinlink_opc-h68k-c-d-f-usb
hinlink_opc-h68k-new
hinlink_opc-h69k
hinlink_opc-h69k-mini
hinlink_h28k_rk3528
hinlink_h29k-v1.3-1.14_rk3528
hinlink_h29k-v5-1.14_rk3528
hinlink_h29k-v5-1.49_rk3528
hinlink_opc-ht2_rk3528
hinlink_opc-h89k_rk3588
hinlink_h88k_v2
hinlink_h88k_v3
"

[ -f include/image.mk ] || { echo "请在 immortalwrt 树根执行"; exit 1; }

echo "[1/5] 写 .config stub（多机型）"
{
	echo "CONFIG_TARGET_rockchip=y"
	echo "CONFIG_TARGET_rockchip_armv8=y"
	echo "CONFIG_TARGET_MULTI_PROFILE=y"
	echo "# CONFIG_TARGET_PER_DEVICE_ROOTFS is not set"
	for d in $DEVICES; do
		echo "CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_${d}=y"
	done
} > .config

echo "[2/5] 清元数据缓存（armv8.mk.hinlink 改动不会被自动跟踪）"
rm -f tmp/.targetinfo tmp/.config-target.in tmp/.packageinfo tmp/.packagedeps \
      tmp/.config-package.in tmp/info/.targetinfo-*

echo "[3/5] make defconfig"
make defconfig

echo "      检查 16 个机型是否都选中："
grep -c '^CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_.*=y$' .config

echo "[4/5] make download -j${JOBS}"
make -j"${JOBS}" download

echo "[5/5] make -j${JOBS}"
make -j"${JOBS}"

echo
echo "完成。产物："
ls -la bin/targets/rockchip/armv8/*.img.gz | wc -l
ls -la bin/targets/rockchip/armv8/*.img.gz
