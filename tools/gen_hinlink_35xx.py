#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RK3528 机型 DTS 生成（immortalwrt）。

★ 修正上一版的错误 ★
上一版我手写 RK3528 DTS，漏了 gmac1_rstn_l（被引用但未定义），
且缺 &sdmmc/&sdhci/&uart/&usb 等基础节点，还留了一堆死label。

本版改为**直接复用 coolsnowwolf/lede 的源码**，只做必要的最小改动：
  1. compatible 保持 lede 原样（已是 hinlink,opc-h29k / hinlink,opc-ht2）
  2. 把 `#include "rk3528.dtsi"` 保持不变（immortalwrt 6.18 内核已有）
  3. H29K 电池版 = H29K + 电池管理占位段（待实机确认）
  4. H28K 直接用 OpenWrt 主线原版

这样保证节点完整性 —— lede 的 DTS 是能编译的（lede 在发布固件）。
"""

import io
import os
import re

OUT = 'immortalwrt/dts'
LED = 'ow'          # lede 源码缓存


def read_lede(name):
    return io.open(os.path.join(LED, name), encoding='utf-8').read()


def normalize(t):
    """统一为 LF，去掉可能存在的 CRLF"""
    return t.replace('\r\n', '\n')


def gen_h28k():
    """H28K：直接用 OpenWrt 主线原版（主线已支持，无需改造）"""
    src = io.open('ow/mainline/rk3528-hinlink-h28k.dts', encoding='utf-8').read()
    return normalize(src)


def gen_h29k(battery=False):
    """H29K：以 lede rk3528-opc-h29k.dts 为基准

    改动仅两处：
    1. 头部注释说明来源与验证状态
    2. 电池版追加电池管理段
    """
    t = read_lede('lede-h29k.dts')

    hdr_old = '// SPDX-License-Identifier: (GPL-2.0+ OR MIT)'
    hdr_new = '''// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/*
 * HinLink OPC-H29K%s —— HinLink 适配 for immortalwrt
 *
 * 本文件基于 coolsnowwolf/lede 的 rk3528-opc-h29k.dts，
 * 仅追加头部说明与%s，**未改动任何硬件配置**。
 *
 * 理由：lede 的 DTS 已在发布固件中验证过可编译，比手写可靠。
 *
 * 硬件要点（来自 lede 源码）：
 *   - 板载 RGMII 网口（gmac1），PCIe 口未在本 DTS 启用
 *   - 板载 SDIO WiFi：复位 GPIO1_A6低有效，host-wake GPIO1_A7
 *   - 4G/5G 双 LED（gpio4 PC0/ PC3）+ 绿色工作灯（gpio4 PB7）
 *   - rfkill 控制 4G/5G 模组（gpio1 PB0）
 *   - 含 SPI 屏接口（st7789v）
 */''' % (' (battery)' if battery else '',
                '电池管理段（待实机确认）' if battery else '本文件内容')

    t = t.replace(hdr_old, hdr_new, 1)

    if battery:
        t += '''
/*
 * ★ 电池版本：以下为占位，需实机补全 ★
 *
 * 未知项（必须实机确认，不能猜）：
 *   - 电量计芯片型号与 I2C 地址
 *   - 充电 IC 型号与使能/状态引脚
 *   - 是否真的有独立电池供电路径（还是仅靠 USB 5V 旁路充电）
 *
 * 取证方法（在刷了 H29K 的机器上执行）：
 *   ls /sys/bus/i2c/devices/
 *   dmesg | grep -iE "bq27|bq25|max17|chg|charg|battery"
 *   cat /sys/class/power_supply/*/uevent
 *   find /sys/bus/i2c/devices/ -name uevent -exec grep -l . {} \\;
 *
 * 拿到数据后再补vcc_chg / gauge / battery 节点与对应 kmod。
 * 在此之前不要凭空填 GPIO —— 填错会导致充电异常甚至损坏电池。
 */
&{/} {
	/* placeholder-battery: 待实机确认后补全 */
};
'''
    return normalize(t)


def gen_ht2():
    """HT2：以 lede rk3528-opc-ht2.dts 为基准"""
    t = read_lede('lede-ht2.dts')
    hdr_old = '// SPDX-License-Identifier: (GPL-2.0+ OR MIT)'
    hdr_new = '''// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/*
 * HinLink OPC-HT2 —— HinLink 适配 for immortalwrt
 *
 * 本文件基于 coolsnowwolf/lede 的 rk3528-opc-ht2.dts，
 * 仅追加头部说明，**未改动任何硬件配置**。
 *
 * 硬件要点（来自 lede 源码）：
 *   - 板载 RGMII 网口（gmac1）
 *   - 板载 SDIO WiFi：复位 GPIO1_A6 低有效，host-wake GPIO1_A7
 *     ※ 与 H29K 的差异：SDIO 最高速率为 SDR50（H29K 是 SDR104）
 *   - 琥珀色 LAN 灯（gpio4 PC0）+ 绿色工作灯（gpio4 PB7）
 *   - 无 4G/5G LED 与 rfkill（H29K 才有）
 */'''
    t = t.replace(hdr_old, hdr_new, 1)
    return normalize(t)


def gen_h88k(v):
    """H88K v2/v3：以 iStoreOS 的 dts 为基准

    iStoreOS 的 rk3588-hinlink.dtsi 不在 immortalwrt 里，
    必须连带移植（见 README）。
    """
    t = read_lede('iso-h88k-%s.dts' % v)
    hdr_old = '// SPDX-License-Identifier: (GPL-2.0+ OR MIT)'
    extra = (' *   - combphy0_ps + sata0（SATA 存储）'
             if v == 'v2' else
             ' *   - pcie2x1l2 + RTL8125 2.5G，&spi4 接 ST7789V 屏\n'
             ' *   - eth_order 显式固定 NIC 与 GMAC 枚举顺序（作者遇到过顺序不稳定）')
    hdr_new = '''// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/*
 * HinLink OPC-H88K %s —— HinLink 适配 for immortalwrt
 *
 * 本文件基于 istoreos/istoreos 的 rk3588-h88k-%s.dts，
 * 仅追加头部说明，未改动硬件配置。
 *
 * ★ 依赖：rk3588-hinlink.dtsi（iStoreOS 私有，immortalwrt 6.18 内核中没有）
 *   必须一并移植，否则编译失败。来源：
 *   https://github.com/istoreos/istoreos
 *     target/linux/rockchip/dts/rk3588/rk3588-hinlink.dtsi
 *   该dtsi 还需下列 iStoreOS 私有 dtsi（在同目录下）：
 *     rk3588-hdmirx.dtsi  rk3588-ramoops.dtsi  rk3588-rk806-single.dtsi
 *     rk3588s-ip.dtsi  rk3588s-ip-supply.dtsi
 *     rk3588s-crypto.dtsi  rk3588s-gpu.dtsi  rk3588s-npu.dtsi  rk3588s-vpu.dtsi
 *
 * 硬件要点：
%s */''' % (v.upper(), v, extra)
    t = t.replace(hdr_old, hdr_new, 1)
    return normalize(t)


if __name__ == '__main__':
    jobs = [
        ('rk3528-hinlink-h28k.dts', gen_h28k(), 'OpenWrt 主线原版'),
        ('rk3528-hinlink-h29k.dts', gen_h29k(False), 'lede 原版 + 头部注释'),
        ('rk3528-hinlink-h29k-battery.dts', gen_h29k(True), 'lede H29K + 电池占位段'),
        ('rk3528-hinlink-ht2.dts', gen_ht2(), 'lede 原版 + 头部注释'),
        ('rk3588-hinlink-h88k-v2.dts', gen_h88k('v2'), 'iStoreOS 原版 + 头部注释'),
        ('rk3588-hinlink-h88k-v3.dts', gen_h88k('v3'), 'iStoreOS 原版 + 头部注释'),
    ]
    print('=== 生成 DTS ===')
    for fn, body, src in jobs:
        p = os.path.join(OUT, fn)
        io.open(p, 'w', encoding='utf-8', newline='\n').write(body)
        print('  %-36s %6d B  (%s)' % (fn, len(body), src))
    print('\n完成：RK3528 4 机型 + RK3588 2 机型')
