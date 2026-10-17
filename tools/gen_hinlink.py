#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚠️⚠️ **已过时（2026-10-12 起）—— 不要再运行本脚本** ⚠️⚠️

本脚本是最初**一次性**生成全机型 DTS / board.d 的生成器。之后所有修正都是
**直接改仓库里的文件**做的，两边早已不同步。现在直跑它会用旧内容
**覆盖掉手工修正**（WAN 映射、屏/风扇参数、H89K 重构、h68k 合并改名等全丢）。

如需参考历史生成逻辑请只读不改；要改机型请直接改
`target/linux/rockchip/files/.../` 下的 DTS 与
`armv8/base-files/etc/board.d/{01_leds,02_network}`。

已知与现状不符的地方（举例，不止这些）：
  * 机型名仍是 `h68k-a / -a-usb / -c / -c-usb3 / -d / -d-usb`
    （现状是 `h68k-a-b / -a-b-usb / -c-d-f / -c-d-f-usb`，见 README §4.14）
  * 02_network 里 h68k 老机器的 WAN 仍写 eth1（2026-10-12 已更正为 eth0）
  * 没有 H29K 1.49 寸触屏版、没有 fbtft 内建段

---

生成 immortalwrt/immortalwrt 的 HinLink 全机型适配（拆分版，每机型独立 DTS）。

设计原则（用户要求：拆分所有机型，不允许自适应）：
  * 每个硬件变体一个独立 .dts + 一个独立 compatible
  * 02_network / 01_leds 每机型独立分支，写死 ethN 映射
  * 不使用 any/动态探测/自适应逻辑

蓝本：OpenWrt 主线 rk3568-hinlink-h68k.dts + rk3568-hinlink-opc.dtsi
硬件事实来源：厂商 2022/2023/2024 固件 dtb（已解包核对）
"""

import io
import os

OUT_DTS = 'immortalwrt/dts'
OUT_FW = 'immortalwrt/files'
os.makedirs(OUT_DTS, exist_ok=True)
os.makedirs(OUT_FW, exist_ok=True)

# ============================================================
# 硬件事实表（全部来自厂商 dtb 反编译核对，无推测）
# ============================================================

# GMAC 时序：跨 2022/2023/2024 三代固件完全一致，且与 OpenWrt 主线一致
GMAC_COMMON = '''&gmac0 {
	assigned-clocks = <&cru SCLK_GMAC0_RX_TX>, <&cru SCLK_GMAC0>;
	assigned-clock-parents = <&cru SCLK_GMAC0_RGMII_SPEED>;
	assigned-clock-rates = <0>, <125000000>;
	clock_in_out = "output";
	phy-mode = "rgmii-id";
	phy-supply = <&vcc3v3_sys>;
	pinctrl-names = "default";
	pinctrl-0 = <&gmac0_miim
		     &gmac0_tx_bus2
		     &gmac0_rx_bus2
		     &gmac0_rgmii_clk
		     &gmac0_rgmii_bus
		     &gmac0_rstn>;
	snps,reset-gpios = <&gpio2 RK_PD3 GPIO_ACTIVE_LOW>;
	snps,reset-active-low;
	snps,reset-delays-us = <0 20000 100000>;
	tx_delay = <0x3c>;
	rx_delay = <0x2f>;
	phy-handle = <&rgmii_phy0>;
	status = "okay";
};

&gmac1 {
	assigned-clocks = <&cru SCLK_GMAC1_RX_TX>, <&cru SCLK_GMAC1>;
	assigned-clock-parents = <&cru SCLK_GMAC1_RGMII_SPEED>;
	assigned-clock-rates = <0>, <125000000>;
	clock_in_out = "output";
	phy-mode = "rgmii-id";
	phy-supply = <&vcc3v3_sys>;
	pinctrl-names = "default";
	pinctrl-0 = <&gmac1m1_miim
		     &gmac1m1_tx_bus2
		     &gmac1m1_rx_bus2
		     &gmac1m1_rgmii_clk
		     &gmac1m1_rgmii_bus
		     &gmac1_rstn>;
	snps,reset-gpios = <&gpio1 RK_PB0 GPIO_ACTIVE_LOW>;
	snps,reset-active-low;
	snps,reset-delays-us = <0 20000 100000>;
	tx_delay = <0x4f>;
	rx_delay = <0x26>;
	phy-handle = <&rgmii_phy1>;
	status = "okay";
};

&mdio0 {
	rgmii_phy0: ethernet-phy@1 {
		compatible = "ethernet-phy-ieee802.3-c22";
		reg = <0x1>;
	};
};

&mdio1 {
	rgmii_phy1: ethernet-phy@1 {
		compatible = "ethernet-phy-ieee802.3-c22";
		reg = <0x1>;
	};
};
'''

# PHY 复位引脚（pinctrl 段，每份 DTS 都要有）
PCFG_RSTN = '''&pinctrl {
	gmac {
		gmac0_rstn: gmac0-rstn {
			rockchip,pins = <2 RK_PD3 RK_FUNC_GPIO &pcfg_pull_none>;
		};

		gmac1_rstn: gmac1-rstn {
			rockchip,pins = <1 RK_PB0 RK_FUNC_GPIO &pcfg_pull_none>;
		};
	};
};
'''

# ---- 2.5G PCIe 说明（重要）----
#
# ★ 主线 rk3568-hinlink-opc.dtsi 已经把两路 2.5G 口的「初始化责任」全部落实：
#     &combphy0/1/2   status = "okay"
#     &pcie30phy       data-lanes = <1 2>       status = "okay"
#     &pcie3x1 { num-lanes=1; reset-gpios=<&gpio3 RK_PA4>; vpcie3v3-supply=<&vcc3v3_pi6c_05>; status="okay"; }
#     &pcie3x2 { num-lanes=1; reset-gpios=<&gpio2 RK_PD0>; vpcie3v3-supply=<&vcc3v3_pi6c_05>; status="okay"; }
#
# ★ 2022 年厂商 dtb 里的 pcie-eth@10,0 / pcie-eth@20,0 子节点**不是**必需的：
#   RTL8125B 是标准 PCI 设备，内核 pcie 驱动 + r8169 模块会在启动时自动枚举，
#   自然产生 eth2/eth3。主线 OpenWrt 从未写这两个节点，H68K 依然是四网口。
#   写入反而可能干扰枚举顺序。
#
# ⇒ 因此本方案**不写 pcie-eth 子节点**，只按机型决定是否 disable PCIe 控制器。
#
# 网口枚举结果：
#   gmac0   -> eth0   (SoC 内部，顺序固定)
#   gmac1   -> eth1   (SoC 内部，顺序固定)
#   pcie3x1 -> eth2   (PCI 扫描)
#   pcie3x2 -> eth3   (PCI 扫描)

PCIE_DISABLE = '''/*
 * 2 网口变体：屏蔽两路 PCIe 2.5G
 * 仅保留 2 个 RGMII 千兆口
 */
&combphy1 {
	status = "disabled";
};

&combphy2 {
	status = "disabled";
};

&pcie3x1 {
	status = "disabled";
};

&pcie3x2 {
	status = "disabled";
};
'''

# 仅屏蔽一路 PCIe（3 口变体）
PCIE_DISABLE_1 = '''/* 精简版：屏蔽第2 路 PCIe 2.5G */
&combphy2 {
	status = "disabled";
};

&pcie3x2 {
	status = "disabled";
};
'''

# ---- AIC8800 SDIO WiFi（a/b 系独有）----
# 引脚来自 2022 a-b dtb + 用户提供的 H69K 点亮脚本交叉验证：
#   sdmmc2m0: data GPIO3_C6..C7 + D0..D1 (0x16-0x19), cmd 0x1a, clk 0x1b, func 3
#   WiFi power enable: gpio3 D5 (0x1d) 高有效
#   host-wake: gpio3 D4 (0x1c)
#   32.768kHz 时钟: RK809 PMIC clkout2 (clocks = <&rk809 1>)
AIC8800_SDIO = '''&sdmmc2 {
	bus-width = <4>;
	cap-sd-highspeed;
	cap-sdio-irq;
	disable-wp;
	keep-power-in-suspend;
	max-frequency = <15000000>;
	mmc-pwrseq = <&sdio_pwrseq>;
	non-removable;
	pinctrl-names = "default";
	pinctrl-0 = <&sdmmc2m0_bus4 &sdmmc2m0_cmd &sdmmc2m0_clk>;
	sd-uhs-sdr25;
	sd-uhs-sdr50;
	sd-uhs-sdr104;
	status = "okay";
	vmmc-supply = <&vcc3v3_sys>;
	vqmmc-supply = <&vcc3v3_sd_pwr>;

	sdio_wifi: sdio-wifi@0 {
		interrupt-parent = <&gpio3>;
		interrupts = <RK_PD4 IRQ_TYPE_LEVEL_HIGH>;
		interrupt-names = "host-wake";
		reg = <0>;
	};
};
'''

AIC8800_POWER = '''&{/} {
	sdio_pwrseq: sdio-pwrseq {
		compatible = "mmc-pwrseq-simple";
		clocks = <&rk809 1>;
		clock-names = "ext_clock";
		pinctrl-names = "default";
		pinctrl-0 = <&wifi_enable>;
		post-power-on-delay-ms = <200>;
		power-off-delay-us = <5000000>;
		reset-gpios = <&gpio3 RK_PD5 GPIO_ACTIVE_LOW>;
	};
};
'''

AIC8800_PINCTRL = '''
&pinctrl {
	sdmmc {
		vcc3v3_sd_pwr_en: vcc3v3-sd-pwr-en {
			rockchip,pins = <0 RK_PA6 RK_FUNC_GPIO &pcfg_pull_none>;
		};

		sdmmc2m0_bus4: sdmmc2m0-bus4 {
			rockchip,pins =
				<3 RK_PC6 RK_FUNC_3 &pcfg_pull_up_drv_level_2>,
				<3 RK_PC7 RK_FUNC_3 &pcfg_pull_up_drv_level_2>,
				<3 RK_PD0 RK_FUNC_3 &pcfg_pull_up_drv_level_2>,
				<3 RK_PD1 RK_FUNC_3 &pcfg_pull_up_drv_level_2>;
		};

		sdmmc2m0_cmd: sdmmc2m0-cmd {
			rockchip,pins = <3 RK_PD2 RK_FUNC_3 &pcfg_pull_up_drv_level_2>;
		};

		sdmmc2m0_clk: sdmmc2m0-clk {
			rockchip,pins = <3 RK_PD3 RK_FUNC_3 &pcfg_pull_up_drv_level_2>;
		};
	};

	wifi {
		wifi_enable: wifi-enable {
			rockchip,pins = <3 RK_PD5 RK_FUNC_GPIO &pcfg_pull_none>;
		};
	};
};
'''

VCC3V3_SD_PWR = '''&{/} {
	vcc3v3_sd_pwr: vcc3v3-sd-pwr {
		compatible = "regulator-fixed";
		enable-active-high;
		gpio = <&gpio0 RK_PA6 GPIO_ACTIVE_HIGH>;
		pinctrl-names = "default";
		pinctrl-0 = <&vcc3v3_sd_pwr_en>;
		regulator-always-on;
		regulator-boot-on;
		regulator-min-microvolt = <3300000>;
		regulator-max-microvolt = <3300000>;
		regulator-name = "vcc3v3_sd_pwr";
		vin-supply = <&vcc5v0_sys>;
	};
};
'''

RTC_HYM8563 = '''&i2c1 {
	hym8563: rtc@51 {
		compatible = "haoyu,hym8563";
		interrupt-parent = <&gpio1>;
		interrupts = <RK_PC4 IRQ_TYPE_EDGE_FALLING>;
		pinctrl-names = "default";
		pinctrl-0 = <&rtc_int>;
		reg = <0x51>;
	};
};
'''

RTC_PINCTRL = '''
&pinctrl {
	rtc {
		rtc_int: rtc-int {
			rockchip,pins = <1 RK_PC4 RK_FUNC_GPIO &pcfg_pull_up>;
		};
	};
};
'''

MODEM_5G = '''&{/} {
	modem_enable: modem-enable {
		compatible = "regulator-fixed";
		enable-active-high;
		gpio = <&gpio0 RK_PC0 GPIO_ACTIVE_LOW>;
		pinctrl-names = "default";
		pinctrl-0 = <&modem_enable_en>;
		regulator-always-on;
		regulator-boot-on;
		regulator-min-microvolt = <3300000>;
		regulator-max-microvolt = <3300000>;
		regulator-name = "modem_enable";
		startup-delay-us = <2000000>;
		vin-supply = <&vcc5v0_sys>;
	};
};
'''

MODEM_PINCTRL = '''
&pinctrl {
	modem {
		modem_enable_en: modem-enable-en {
			rockchip,pins = <0 RK_PC0 RK_FUNC_GPIO &pcfg_pull_none>;
		};
	};
};
'''

# RK809 PMIC 需要引出时钟输出（供 AIC8800 32.768kHz）
RK809_EXTCLK = '''&rk809 {
	ext_32k_clk_out: ext-clk-32k-out {
		rockchip,grf = <&rk809_grf 0>;
		#clock-cells = <1>;
		clock-output-rate = <32768>;
	};
};
'''

# ============================================================
# 机型定义表
# ============================================================
# 字段：dts 文件名、model、compatible、额外内容块、网口映射(lan,wan)、led 块
#
# 网口映射来源：
#   a/b 系  : 2022 dtb 无 pcie-eth，仅 2 个 GMAC  -> LAN 'eth1' / WAN 'eth0'
#   c/d/f 系: 2022 dtb 有 2× RTL8125 PCIe       -> LAN 'eth0 eth1 eth2' / WAN 'eth3'
#   h68k-new: 2023.4.20 把WAN 改为 eth0          -> LAN 'eth1 eth2 eth3' / WAN 'eth0'
#   h69k    : 屏蔽 1 个 GMAC，仅 1 GMAC + 2 PCIe -> LAN 'eth1 eth2' / WAN 'eth0'

MACHINES = [
    # ---- H68K A/B：2022 双千兆版（2×GMAC，无 2.5G，SDIO WiFi，带 RTC）----
    dict(
        name='h68k-a',
        model='HinLink OPC-H68K A/B',
        compat='hinlink,opc-h68k-a',
        extra=[PCIE_DISABLE, AIC8800_POWER, VCC3V3_SD_PWR, AIC8800_SDIO,
               RTC_HYM8563, RK809_EXTCLK, AIC8800_PINCTRL, RTC_PINCTRL],
        lan='eth1', wan='eth0',
        alt_vendor='LinkStar', alt_model='H68K A/B',
        packages='',
        note='2022 老机器：2 个千兆口，无 2.5G，板载 SDIO WiFi（AP6256/Broadcom）+ RTC',
        wifi='sdio_ap6256',
    ),
    # ---- H68K C/D/F：2022 四网口版（2×GMAC + 2×RTL8125 2.5G）----
    dict(
        name='h68k-c',
        model='HinLink OPC-H68K C/D/F',
        compat='hinlink,opc-h68k-c',
        extra=[],
        lan='eth0 eth2 eth3', wan='eth1',
        alt_vendor='LinkStar', alt_model='H68K C/D/F',
        packages='',
        note='2022 版：2×RTL8125 2.5G + 2×千兆，无板载 WiFi',
    ),
    # ---- H68K C USB3：2022 四网口 + USB3.0 改型 ----
    dict(
        name='h68k-c-usb3',
        model='HinLink OPC-H68K C USB3',
        compat='hinlink,opc-h68k-c-usb3',
        extra=[],
        lan='eth0 eth2 eth3', wan='eth1',
        alt_vendor='LinkStar', alt_model='H68K C USB3',
        packages='',
        note='2022.8 版：C/D/F 基础上改USB 3.0',
    ),
    # ---- H68K D：2023.4 推荐版（网口全识别，WAN 改 eth0）----
    dict(
        name='h68k-d',
        model='HinLink OPC-H68K D',
        compat='hinlink,opc-h68k-d',
        extra=[],
        lan='eth1 eth2 eth3', wan='eth0',
        alt_vendor='LinkStar', alt_model='H68K D',
        packages='',
        note='2023.4 推荐版：2×RTL8125 2.5G，WAN 从 eth1 改为 eth0（网口全识别）',
    ),
    # ---- H68K New：2023末~2024 现行版（与 H69K 共底板）----
    dict(
        name='h68k-new',
        model='HinLink OPC-H68K (2023 new board)',
        compat='hinlink,opc-h68k-new',
        extra=[AIC8800_POWER, VCC3V3_SD_PWR, AIC8800_SDIO,
               RK809_EXTCLK, AIC8800_PINCTRL],
        lan='eth1 eth2 eth3', wan='eth0',
        alt_vendor='LinkStar', alt_model='H68K',
        packages='',
        note='2023末改用 H69K 底板出货；带 AIC8800 SDIO WiFi',
        wifi='sdio_aic8800',
    ),
    # ---- H69K：H68K 底板 + USB 5G模组 + 屏蔽 1 个 GMAC ----
    dict(
        name='h69k',
        model='HinLink OPC-H69K (5G)',
        compat='hinlink,opc-h69k',
        extra=[AIC8800_POWER, VCC3V3_SD_PWR, AIC8800_SDIO,
               RK809_EXTCLK, AIC8800_PINCTRL, MODEM_5G, MODEM_PINCTRL],
        lan='eth1 eth2', wan='eth0',
        alt_vendor=None, alt_model=None,
        packages='kmod-hwmon-pwmfan kmod-usb-serial-option',
        note='真·69K：装 USB 5G 模组；屏蔽 1 个 GMAC → 1×GMAC + 2×RTL8125 = 3 口',
        wifi='sdio_aic8800', gmac1_disabled=True,
    ),
    # ---- H69K mini：屏蔽网口的精简版（= h68k-max 同形态）----
    dict(
        name='h69k-mini',
        model='HinLink OPC-H69K mini',
        compat='hinlink,opc-h69k-mini',
        extra=[PCIE_DISABLE_1],
        lan='eth1', wan='eth0',
        alt_vendor=None, alt_model=None,
        packages='',
        note='体积精简版：屏蔽 1 个 GMAC + 1 路 PCIe → 2 口',
        gmac1_disabled=True,
    ),
]

# ============================================================
# DTS 生成
# ============================================================

DTS_HEAD = '''// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/*
 * {model}
 *
 * HinLink 适配for immortalwrt —— 每机型独立 DTS，不做自适应。
 *
 * 硬件事实来源：厂商 {vendor_fw} 固件 dtb（已解包反编译逐项核对）
 * 蓝本：OpenWrt 主线 rk3568-hinlink-h68k.dts
 *
 * {note}
 */

/dts-v1/;

#include "rk3568-hinlink-opc.dtsi"

/ {{
	model = "{model}";
	compatible = "{compat}", "rockchip,rk3568";

{aliases}}};'''

ALIASES_2GMAC = '''	aliases {
		ethernet0 = &gmac0;
		ethernet1 = &gmac1;
	};
'''

ALIASES_1GMAC = '''	aliases {
		ethernet0 = &gmac0;
	};
'''


def gen_dts(m):
    vendor_fw = '2022 R22.7.19/R22.8.22'
    if m['name'] in ('h68k-d',):
        vendor_fw = '2023 R23.4.20'
    elif m['name'] in ('h68k-new', 'h69k', 'h69k-mini'):
        vendor_fw = '2024 QWRT R24.07.07'
    elif m['name'] == 'h68k-c-usb3':
        vendor_fw = '2022 R22.8.22 (armv8-h68k-c)'

    aliases = ALIASES_1GMAC if m.get('gmac1_disabled') else ALIASES_2GMAC

    parts = [DTS_HEAD.format(model=m['model'], compat=m['compat'],
                             vendor_fw=vendor_fw, note=m['note'],
                             aliases=aliases)]

    body = GMAC_COMMON
    if m.get('gmac1_disabled'):
        # 屏蔽 gmac1：整段删除，改为一段空的 disabled 覆盖
        # （DTS 里后定义覆盖先定义，故直接给出 status=disabled 即可）
        g1_start = body.index('&gmac1 {')
        g1_end = body.index('&mdio0 {')
        body = (body[:g1_start]
                + '&gmac1 {\n\tstatus = "disabled";\n};\n\n'
                + body[g1_end:])
    parts.append(body)

    for blk in m['extra']:
        parts.append(blk)

    parts.append(PCFG_RSTN)

    fn = os.path.join(OUT_DTS, 'rk3568-hinlink-%s.dts' % m['name'])
    io.open(fn, 'w', encoding='utf-8', newline='\n').write('\n'.join(parts))
    return fn


# ============================================================
# 02_network —— 每机型独立分支，写死映射
# ============================================================
NET_HEADER = '''#!/bin/sh /lib/ucode/luci

# HinLink 机型网络配置
#
# 每机型独立分支，映射写死，不做自适应探测。
# 依据：厂商 2022/2023/2024 固件的 board.d/02_network 原文
#
# 命名对照（厂商曾用过的 compatible 前缀）：
#   hinlink,opc-h68k-a / -c      2022 五改型（a-b / c-d / c-d-f / c-usb3）
#   hinlink,opc-h68k-d            2023.4 推荐版
#   hinlink,opc-h68k-new          2023末~2024（与 H69K 共底板）
#   hinlink,opc-h69k              装 USB 5G 模组的真 69K
#   hinlink,opc-h69k-mini         体积精简版
#
# 网口枚举前提（immortalwrt 6.18 内核 dtc顺序）：
#   gmac0     -> eth0   (SoC 内部控制器，顺序固定)
#   gmac1     -> eth1   (SoC 内部控制器，顺序固定)
#   rtl8125_1 -> eth2   (PCIe，按 PCI 扫描顺序)
#   rtl8125_2 -> eth3   (PCIe)
# ⚠️ 若某机型无 pcie-eth，则不存在 eth2/eth3，下方映射已按实际配置写死。

'''


def gen_02_network():
    lines = [NET_HEADER]
    lines.append('case "$board" in\n')
    lines.append('# ---- H68K A/B：2022 双千兆版，仅 2 个口----\n')
    lines.append("""hinlink,opc-h68k-a|\\
	linkstar,opc-h68k-a)
		ucidef_set_interfaces_lan_wan '%s' '%s'
		;;
""" % (MACHINES[0]['lan'], MACHINES[0]['wan']))
    lines.append('\n# ---- H68K C/D/F：2022 四网口版，2×RTL8125 ----\n')
    lines.append("""hinlink,opc-h68k-c|\\
	linkstar,opc-h68k-c)
		ucidef_set_interfaces_lan_wan '%s' '%s'
		;;
""" % (MACHINES[1]['lan'], MACHINES[1]['wan']))
    lines.append('\n# ---- H68K C USB3：2022 四网口 + USB3 ----\n')
    lines.append("""hinlink,opc-h68k-c-usb3)
		ucidef_set_interfaces_lan_wan '%s' '%s'
		;;
""" % (MACHINES[2]['lan'], MACHINES[2]['wan']))
    lines.append('\n# ---- H68K D：2023.4 推荐版，WAN = eth0（网口全识别）----\n')
    lines.append("""hinlink,opc-h68k-d|\\
	linkstar,opc-h68k-d)
		ucidef_set_interfaces_lan_wan '%s' '%s'
		;;
""" % (MACHINES[3]['lan'], MACHINES[3]['wan']))
    lines.append('\n# ---- H68K new：2023末~2024 现行版 ----\n')
    lines.append("""hinlink,opc-h68k-new)
		ucidef_set_interfaces_lan_wan '%s' '%s'
		;;
""" % (MACHINES[4]['lan'], MACHINES[4]['wan']))
    lines.append('\n# ---- H69K：屏蔽 1 个 GMAC ----\n')
    lines.append("""hinlink,opc-h69k)
		ucidef_set_interfaces_lan_wan '%s' '%s'
		;;
""" % (MACHINES[5]['lan'], MACHINES[5]['wan']))
    lines.append('\n# ---- H69K mini：精简版 ----\n')
    lines.append("""hinlink,opc-h69k-mini)
		ucidef_set_interfaces_lan_wan '%s' '%s'
		;;
""" % (MACHINES[6]['lan'], MACHINES[6]['wan']))
    lines.append('\n# ---- H66K：无板载网口，单口 ----\n')
    lines.append("""hinlink,h66k)
		ucidef_set_interfaces_lan_wan 'eth0' 'eth1'
		;;
""")
    lines.append('\n# ---- H28K：RK3528，双口 ----\n')
    lines.append("""hinlink,h28k)
		ucidef_set_interfaces_lan_wan 'eth0' 'eth1'
		;;
""")
    lines.append('''
	*)
		;;
esac
''')
    # MAC 地址生成
    lines.append('''
# 从 eMMC CID 生成稳定的 MAC
case "$board" in
hinlink,opc-h68k-a|\\
hinlink,opc-h68k-c|\\
hinlink,opc-h68k-c-usb3|\\
hinlink,opc-h68k-d|\\
hinlink,opc-h68k-new|\\
hinlink,opc-h69k|\\
hinlink,opc-h69k-mini|\\
hinlink,h68k|\\
hinlink,h66k|\\
hinlink,h28k)
		wan_mac=$(macaddr_generate_from_mmc_cid mmcblk0)
		lan_mac=$(macaddr_add "$wan_mac" 1)
		;;
esac
''')

    fn = os.path.join(OUT_FW, '02_network_hinlink')
    io.open(fn, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    return fn


# ============================================================
# 01_leds
# ============================================================
LEDS_HEADER = '''#!/bin/sh /lib/ucode/luci

# HinLink 机型 LED 配置
#
# 每机型独立分支。LED 颜色与 GPIO 来自厂商 dtb 的 gpio-leds / leds 节点。
# ⚠️ 下列 color/label 需按实机确认后调整；未列出的LED 保持默认（常亮或��灭）。

'''

LEDS = [
    ('H68K A/B', ['hinlink,opc-h68k-a', 'linkstar,opc-h68k-a'],
     '\tucidef_set_led_default "power" "POWER" "green:work" "1"\n'
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth0"\n'),
    ('H68K C/D/F', ['hinlink,opc-h68k-c', 'linkstar,opc-h68k-c'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth3"\n'
     '\tucidef_set_led_ide "disk" "DISK" "yellow:disk"\n'),
    ('H68K C USB3', ['hinlink,opc-h68k-c-usb3'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth3"\n'),
    ('H68K D', ['hinlink,opc-h68k-d', 'linkstar,opc-h68k-d'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth0"\n'),
    ('H68K new', ['hinlink,opc-h68k-new'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth0"\n'),
    ('H69K', ['hinlink,opc-h69k'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth0"\n'),
    ('H69K mini', ['hinlink,opc-h69k-mini'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth0"\n'),
    ('H66K', ['hinlink,h66k'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:net" "eth0"\n'),
    ('H28K', ['hinlink,h28k'],
     '\tucidef_set_led_netdev "wan" "WAN" "blue:wan" "eth1"\n'
     '\tucidef_set_led_netdev "lan" "LAN" "amber:lan" "eth0"\n'),
]


def gen_01_leds():
    lines = [LEDS_HEADER, 'case "$board" in\n']
    for title, boards, blk in LEDS:
        lines.append('\n# ---- %s ----\n' % title)
        for i, b in enumerate(boards):
            last = (i == len(boards) - 1)
            sep = '' if last else '|\\\n\t'
            lines.append('%s%s\n' % (b, sep))
        lines.append(blk)
        lines.append('\t;;\n')
    lines.append('\n\t*)\n\t\t;;\nesac\n')

    fn = os.path.join(OUT_FW, '01_leds_hinlink')
    io.open(fn, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    return fn


# ============================================================
# armv8.mk 设备定义
# ============================================================
def gen_armv8mk():
    lines = ['\n# ===== HinLink 全机型（每机型独立，不做自适应） =====\n',
             '\ndefine Device/hinlink_h6xk_base\n',
             '  $(Device/rk3568)\n',
             '  DEVICE_VENDOR := HINLINK\n',
             '  DEVICE_PACKAGES := kmod-ata-ahci-dwc kmod-r8169 wpad-basic-mbedtls\n',
             'endef\n',
             '\n# M.2 (PCIe) 无线模块机型\n',
             'define Device/hinlink_h6xk_m2_wifi\n',
             '  $(Device/hinlink_h6xk_base)\n',
             '  DEVICE_PACKAGES += kmod-mt7921e\n',
             'endef\n',
             '\n# 板载 SDIO 无线（AIC8800，全新机器）\n',
             'define Device/hinlink_h6xk_sdio_aic8800\n',
             '  $(Device/hinlink_h6xk_base)\n',
             '  DEVICE_PACKAGES += kmod-aic8800s\n',
             'endef\n',
             '\n# 板载 SDIO 无线（AP6256，老机器 Broadcom brcmfmac）\n',
             'define Device/hinlink_h6xk_sdio_ap6256\n',
             '  $(Device/hinlink_h6xk_base)\n',
             '  DEVICE_PACKAGES += kmod-brcmfmac kmod-firmware-brcm80211\n',
             'endef\n']

    for m in MACHINES:
        lines.append('\ndefine Device/hinlink_opc-%s\n' % m['name'])
        lines.append('  $(Device/hinlink_h6xk_%s)\n' % m.get('wifi', 'm2_wifi'))
        lines.append('  DEVICE_MODEL := %s\n' % m['model'].replace('HinLink OPC-', ''))
        if m.get('alt_vendor'):
            lines.append('  DEVICE_ALT0_VENDOR := %s\n' % m['alt_vendor'])
            lines.append('  DEVICE_ALT0_MODEL := %s\n' % m['alt_model'])
        lines.append('  DEVICE_DTS := rk3568-hinlink-%s\n' % m['name'])
        lines.append('  UBOOT_DEVICE_NAME := hinlink-%s-rk3568\n' % m['name'])
        if m['packages']:
            lines.append('  DEVICE_PACKAGES += %s\n' % m['packages'])
        lines.append('endef\n')
        lines.append('TARGET_DEVICES += hinlink_opc-%s\n' % m['name'])

    fn = os.path.join('immortalwrt', 'armv8.mk.hinlink')
    io.open(fn, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    return fn


if __name__ == '__main__':
    print('=== 生成 DTS ===')
    for m in MACHINES:
        print('  ', gen_dts(m))
    print('\n=== 生成 02_network ===')
    print('  ', gen_02_network())
    print('\n=== 生成 01_leds ===')
    print('  ', gen_01_leds())
    print('\n=== 生成 armv8.mk 片段 ===')
    print('  ', gen_armv8mk())
    print('\n完成：%d 个机型' % len(MACHINES))
