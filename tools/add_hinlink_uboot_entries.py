#!/usr/bin/env python3
"""在 uboot-rockchip/Makefile 里加入 HINLINK 的 u-boot 条目（照上游 openwrt/main）。

上游 openwrt/main 的条目只登记了 hinlink_h28k / hinlink_h66k / hinlink_h68k
三个设备名；本仓库的机型是按变体拆分的（h68k-a / -c / -c-usb3 / ... / h69k），
所以 BUILD_DEVICES 要把这些名字都登记进去 —— OpenWrt 的 u-boot 包靠
BUILD_DEVICES 反向关联设备，不登记的话 `make defconfig` 会把
CONFIG_PACKAGE_u-boot-hinlink-h68k-rk3568 丢掉（实测过）。

用法：python3 add_hinlink_uboot_entries.py <path/to/uboot-rockchip>
"""
import io
import os
import sys

ENTRIES = """
define U-Boot/hinlink-h28k-rk3528
  $(U-Boot/rk3528/Default)
  NAME:=HINLINK H28K
  BUILD_DEVICES:= \\
    hinlink_h28k_rk3528
endef

define U-Boot/hinlink-h66k-rk3568
  $(U-Boot/rk3568/Default)
  NAME:=HINLINK H66K
  BUILD_DEVICES:= \\
    hinlink_opc-h66k
endef

define U-Boot/hinlink-h68k-rk3568
  $(U-Boot/rk3568/Default)
  NAME:=HINLINK H68K
  BUILD_DEVICES:= \\
    hinlink_opc-h68k-a \\
    hinlink_opc-h68k-a-usb \\
    hinlink_opc-h68k-c \\
    hinlink_opc-h68k-c-usb3 \\
    hinlink_opc-h68k-d \\
    hinlink_opc-h68k-d-usb \\
    hinlink_opc-h68k-new \\
    hinlink_opc-h69k \\
    hinlink_opc-h69k-mini
endef

"""

# 第二组：H29K / HT2（本仓库自建，见 patches-uboot/108-*.patch）
ENTRIES_LOCAL = """
define U-Boot/hinlink-h29k-rk3528
  $(U-Boot/rk3528/Default)
  NAME:=HINLINK H29K
  BUILD_DEVICES:= \\
    hinlink_h29k-v1.3-1.14_rk3528 \\
    hinlink_h29k-v5-1.14_rk3528 \\
    hinlink_h29k-v5-1.49_rk3528
endef

define U-Boot/hinlink-ht2-rk3528
  $(U-Boot/rk3528/Default)
  NAME:=HINLINK OPC-HT2
  BUILD_DEVICES:= \\
    hinlink_opc-ht2_rk3528
endef

"""

# 第三组：RK3588 三款（本仓库自建，见 patches-uboot/109-*.patch）
ENTRIES_RK3588 = """
define U-Boot/hinlink-h88k-v2-rk3588
  $(U-Boot/rk358x/Default)
  NAME:=HINLINK H88K V2
  BUILD_DEVICES:= \\
    hinlink_h88k_v2
endef

define U-Boot/hinlink-h88k-v3-rk3588
  $(U-Boot/rk358x/Default)
  NAME:=HINLINK H88K V3
  BUILD_DEVICES:= \\
    hinlink_h88k_v3
endef

define U-Boot/hinlink-h89k-rk3588
  $(U-Boot/rk358x/Default)
  NAME:=HINLINK H89K
  BUILD_DEVICES:= \\
    hinlink_opc-h89k_rk3588
endef

"""

# 插到 rk3568 段落里（easepi-r1 之前），确保 U-Boot/rk3568/Default 已定义
ANCHOR = 'define U-Boot/easepi-r1-rk3568\n'

# ★ 只定义 U-Boot/xxx 还不够 —— 包由 BuildPackage/U-Boot 遍历 UBOOT_TARGETS
#   展开（include/u-boot.mk 第 144-151 行），列表里没有就不会生成包，
#   make defconfig 也会把 CONFIG_PACKAGE_u-boot-xxx 丢掉。
TARGET_ANCHOR_RK3528 = '  mangopi-m28c-rk3528 \\\n'
TARGET_INSERT_RK3528 = '  hinlink-h28k-rk3528 \\\n'
TARGET_ANCHOR_RK3568 = '  fastrhino-r68s-rk3568 \\\n'
TARGET_INSERT_RK3568 = '  hinlink-h66k-rk3568 \\\n  hinlink-h68k-rk3568 \\\n'


def main():
    pkg = sys.argv[1]
    path = os.path.join(pkg, 'Makefile')
    t = io.open(path, encoding='utf-8').read()
    changed = False

    # --- 1) U-Boot/xxx 条目定义 ---
    if 'U-Boot/hinlink-h68k-rk3568' in t:
        print('[跳过] U-Boot/hinlink-* 条目已存在')
    elif ANCHOR in t:
        t = t.replace(ANCHOR, ENTRIES.lstrip('\n') + ANCHOR, 1)
        changed = True
        print('[改] 已插入 3 个 U-Boot/hinlink-* 条目定义')
    else:
        print('!! 条目锚点未找到：%s' % ANCHOR.strip())
        sys.exit(1)

    # --- 1b) 本仓库自建：H29K / HT2（板级支持见 patches-uboot/108-*.patch）---
    if 'U-Boot/hinlink-h29k-rk3528' in t:
        print('[跳过] U-Boot/hinlink-h29k-rk3528 已存在')
    elif ANCHOR in t:
        t = t.replace(ANCHOR, ENTRIES_LOCAL.lstrip('\n') + ANCHOR, 1)
        changed = True
        print('[改] 已插入 H29K / HT2 的 U-Boot 条目')
    else:
        print('!! 条目锚点未找到')

    # --- 1c) 本仓库自建：RK3588 三款（见 patches-uboot/109-*.patch）---
    if 'U-Boot/hinlink-h89k-rk3588' in t:
        print('[跳过] U-Boot/hinlink-*-rk3588 已存在')
    elif ANCHOR in t:
        t = t.replace(ANCHOR, ENTRIES_RK3588.lstrip('\n') + ANCHOR, 1)
        changed = True
        print('[改] 已插入 RK3588 的 U-Boot 条目（h88k-v2 / h88k-v3 / h89k）')
    else:
        print('!! 条目锚点未找到')

    # --- 2) UBOOT_TARGETS 变体列表 ---
    if TARGET_ANCHOR_RK3528 not in t:
        print('!! UBOOT_TARGETS 的 rk3528 锚点未找到')
    elif TARGET_INSERT_RK3528 in t:
        print('[跳过] UBOOT_TARGETS 里已有 hinlink-h28k-rk3528')
    else:
        t = t.replace(TARGET_ANCHOR_RK3528,
                      TARGET_INSERT_RK3528 + TARGET_ANCHOR_RK3528, 1)
        changed = True
        print('[改] UBOOT_TARGETS += hinlink-h28k-rk3528')

    # --- 2b) UBOOT_TARGETS 里加 H29K / HT2 ---
    T32_INSERT = '  hinlink-h29k-rk3528 \\\n  hinlink-ht2-rk3528 \\\n'
    if T32_INSERT in t:
        print('[跳过] UBOOT_TARGETS 里已有 h29k / ht2')
    elif TARGET_INSERT_RK3528 in t:
        t = t.replace(TARGET_INSERT_RK3528,
                      TARGET_INSERT_RK3528 + T32_INSERT, 1)
        changed = True
        print('[改] UBOOT_TARGETS += hinlink-h29k-rk3528 / hinlink-ht2-rk3528')
    else:
        print('!! 找不到 hinlink-h28k-rk3528 锚点，h29k/ht2 未加入 UBOOT_TARGETS')

    # --- 2c) UBOOT_TARGETS 里加 RK3588 三款 ---
    # 用 2b 刚插入的 hinlink-ht2-rk3528 作锚点（它在 2b 之后必定存在）
    T8_ANCHOR = '  hinlink-ht2-rk3528 \\\n'
    T8_INSERT = ('  hinlink-h88k-v2-rk3588 \\\n'
                 '  hinlink-h88k-v3-rk3588 \\\n'
                 '  hinlink-h89k-rk3588 \\\n')
    if T8_INSERT in t:
        print('[跳过] UBOOT_TARGETS 里已有 RK3588 三款')
    elif T8_ANCHOR in t:
        t = t.replace(T8_ANCHOR, T8_ANCHOR + T8_INSERT, 1)
        changed = True
        print('[改] UBOOT_TARGETS += h88k-v2 / h88k-v3 / h89k（RK3588）')
    else:
        print('!! 找不到 ht2 锚点，RK3588 三款未加入 UBOOT_TARGETS')

    if TARGET_ANCHOR_RK3568 not in t:
        print('!! UBOOT_TARGETS 的 rk3568 锚点未找到')
    elif TARGET_INSERT_RK3568 in t:
        print('[跳过] UBOOT_TARGETS 里已有 hinlink-h66k/h68k-rk3568')
    else:
        t = t.replace(TARGET_ANCHOR_RK3568,
                      TARGET_ANCHOR_RK3568 + TARGET_INSERT_RK3568, 1)
        changed = True
        print('[改] UBOOT_TARGETS += hinlink-h66k-rk3568 / hinlink-h68k-rk3568')

    if changed:
        io.open(path, 'w', encoding='utf-8', newline='\n').write(t)
        print('已写入 %s' % path)
    else:
        print('无需改动')


if __name__ == '__main__':
    main()
