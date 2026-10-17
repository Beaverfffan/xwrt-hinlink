#!/usr/bin/env python3
"""把 armv8.mk.hinlink 里各机型的 u-boot 设置改为上游 OpenWrt 的 HINLINK 方案。

背景
----
上游 openwrt/main 的 package/boot/uboot-rockchip/Makefile 里本来就有：

    define U-Boot/hinlink-h28k-rk3528   BUILD_DEVICES:= hinlink_h28k
    define U-Boot/hinlink-h66k-rk3568   BUILD_DEVICES:= hinlink_h66k
    define U-Boot/hinlink-h68k-rk3568   BUILD_DEVICES:= hinlink_h68k

对应的 defconfig 与 u-boot dts 由 patches/106 / 107 提供。
本仓库原先因「找不到 hinlink defconfig」而把 BOOT_FLOW 清空 / 借用 sige3，
现在改为直接引用上游条目。

用法
----
    python3 fix_uboot_devname.py <armv8.mk.hinlink> [--apply]
不加 --apply 只打印将要做的改动。
"""
import io
import re
import sys

# DTS 前缀 -> 上游 u-boot 条目名
UBOOT_OF = {
    'rk3568-hinlink-h66k': 'hinlink-h66k-rk3568',
    'rk3568-hinlink-h68k': 'hinlink-h68k-rk3568',   # 含 h68k-* 与 h69k*
    'rk3568-hinlink-h69k': 'hinlink-h68k-rk3568',
    'rk3528-hinlink-h28k': 'hinlink-h28k-rk3528',
    # 下面两项是本仓库自建（板级支持见 patches-uboot/108-*.patch）
    'rk3528-hinlink-h29k': 'hinlink-h29k-rk3528',   # 3 个变体共用一个 u-boot
    'rk3528-hinlink-ht2': 'hinlink-ht2-rk3528',
    # RK3588 三款（板级支持见 patches-uboot/109-*.patch）
    'rk3588-hinlink-h88k-v2': 'hinlink-h88k-v2-rk3588',
    'rk3588-hinlink-h88k-v3': 'hinlink-h88k-v3-rk3588',
    'rk3588-hinlink-h89k': 'hinlink-h89k-rk3588',
}

NOTE_OK = """  # ★ u-boot：直接用**上游 OpenWrt 的 HINLINK 支持**（见 patches-uboot/）
  #   上游 package/boot/uboot-rockchip/Makefile 已有本条目，defconfig 与
  #   u-boot dts 由 patches-uboot/ 里那两个 patch 提供（源自 openwrt/main
  #   patches/106、107）。u-boot 2026.07 的
  #   dts/upstream/src/arm64/rockchip/ 里已自带 rk3568-hinlink-h68k.dts。
  #   TPL/ATF 走通用 rk3568_ddr_1560MHz + bl31，不依赖具体板子。
  #   BUILD_DEVICES 已在我们的 Makefile 补丁里登记本机型，
  #   ⇒ make defconfig 会自动带上 CONFIG_PACKAGE_u-boot-{name}=y。
  UBOOT_DEVICE_NAME := {name}
"""

NOTE_NONE = """  # ★ 暂不打包 u-boot：上游 OpenWrt 只为 **H28K / H66K / H68K** 提供了
  #   HINLINK u-boot 条目（defconfig 见 openwrt/main patches/106、107），
  #   本机型没有对应 defconfig，直接写 UBOOT_DEVICE_NAME 会因 dd 找不到
  #   u-boot-rockchip.bin 而编译失败。保持 BOOT_FLOW 为空（不写 u-boot 区）。
  #   如需 u-boot：可参照同 SoC 的 hinlink-h28k-rk3528 / hinlink-h68k-rk3568
  #   新增条目，但需先确认 DDR 参数与 PMIC。
  BOOT_FLOW :=
"""

# 匹配「旧的 u-boot 设置块」：注释若干行 + 空的 BOOT_FLOW :=
# 只处理 BOOT_FLOW 为空的块（即还没指定 u-boot 的机型）。
OLD = re.compile(
    r'^  # ★[^\n]*\n'
    r'(?:  #[^\n]*\n)*'
    r'  BOOT_FLOW\s*:=\s*\n',
    re.M)


def main():
    path = sys.argv[1]
    apply = '--apply' in sys.argv
    text = io.open(path, encoding='utf-8').read()

    blocks = list(re.finditer(r'^define (Device/[^\n]+)\n(.*?)^endef', text, re.S | re.M))
    out = []
    last = 0
    n_ok = n_skip = 0
    for m in blocks:
        name, body = m.group(1), m.group(2)
        dts_m = re.search(r'DEVICE_DTS\s*:?=\s*(\S+)', body)
        if not dts_m:
            continue
        dts = dts_m.group(1)
        ub = None
        for prefix, entry in UBOOT_OF.items():
            if dts.startswith(prefix):
                ub = entry
                break
        new_note = (NOTE_OK.format(name=ub) if ub else NOTE_NONE)
        new_body, cnt = OLD.subn(new_note, body, count=1)
        if cnt == 0:
            print('  [跳过] %-38s 未找到旧 u-boot 设置块' % name)
            continue
        if ub:
            n_ok += 1
            print('  [改] %-38s -> UBOOT_DEVICE_NAME := %s' % (name, ub))
        else:
            n_skip += 1
            print('  [保留] %-38s 无上游 defconfig，维持 BOOT_FLOW 空' % name)
        out.append(text[last:m.start(2)])
        out.append(new_body)
        last = m.end(2)
    out.append(text[last:])
    result = ''.join(out)

    print()
    print('统计：引用上游 u-boot %d 个设备，保留空 BOOT_FLOW %d 个' % (n_ok, n_skip))
    if apply:
        io.open(path, 'w', encoding='utf-8', newline='\n').write(result)
        print('已写入 %s' % path)
    else:
        print('（未写入，加 --apply 生效）')


if __name__ == '__main__':
    main()
