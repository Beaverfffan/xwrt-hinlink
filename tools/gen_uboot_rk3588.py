#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 H88K v2/v3 与 H89K 的 U-Boot 支持 patch。

这三款是 RK3588。与 RK3528 那批不同，u-boot 里没有任何 hinlink 的 RK3588
板级 dts，也没有 rk806 dtsi，因此这里为它们各写一份**精简的 U-Boot 专用
板级 dts**（只含 eMMC / TF 卡 / 调试串口）。

★ 为什么不带 rk806 PMIC 节点
  RK3588 的 PMIC 由 Rockchip TPL（rk3588_ddr_lp4_2112MHz_lp5_2400MHz_v1.19.bin）
  在 SPL 之前就初始化好（DDR 需要电压），U-Boot proper 阶段不需要再配一遍。
  不带 PMIC 节点可以让 u-boot 的板级 dts 保持在最小集，避免抄错 34 路
  regulator 电压反而把板子拉坏。
  ⚠️ 代价：U-Boot 下无法读取/调整 PMIC。若日后需要（例如控制某路电源做
     掉电重启），再按板子原理图补 rk806 节点。

★ eMMC / TF 卡 / 串口 依据
  - H88K v2/v3：来自本仓库的 rk3588-hinlink.dtsi（iStoreOS 成熟配置）
  - H89K      ：来自厂商 dtb（vendor-h89k.dtb）实测
      /mmc@fe2c0000 (sdmmc) bus-width 4, cd-gpios gpio0 PA4 低有效,
                            no-mmc, sd-uhs-sdr104           → TF 卡
      /mmc@fe2e0000 (sdhci) bus-width 8, non-removable,
                            mmc-hs200-1_8v                  → eMMC
      /serial@feb50000      uart2, okay                     → 调试串口
  两者一致，故三份 dts 结构相同。

★ defconfig 基于 u-boot 自带的 generic-rk3588_defconfig，
  target 沿用 CONFIG_TARGET_EVB_RK3588（与上游 generic-rk3588 的做法一致 ——
  RK3588 需要一个 CONFIG_TARGET_* 提供板级支持代码）。
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # tools/ -> repo2/
PATCH = os.path.join(ROOT, 'patches-uboot',
                     '109-board-rockchip-add-hinlink-rk3588-uboot.patch')

DTS = '''// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/*
 * {model}
 *
 * ★ U-Boot 专用板级设备树（RK3588），与内核的 rk3588-hinlink-*.dts 相互独立。
 *   只保留 U-Boot 阶段需要的：eMMC / TF 卡 / 调试串口。
 *
 * ★ 不含 rk806 PMIC
 *   RK3588 的 PMIC 由 Rockchip TPL 在 SPL 之前初始化（DDR 需要电压），
 *   U-Boot proper 不必再配一遍。这样可以让本文件保持最小集，
 *   避免抄错 34 路 regulator 电压。代价是 U-Boot 下读不到 PMIC。
 *
 * ★ 存储与串口依据（厂商 dtb / rk3588-hinlink.dtsi 实测，两者一致）
 *     sdhci  eMMC  bus-width 8, non-removable, mmc-hs200-1_8v
 *     sdmmc  TF 卡 bus-width 4, cd-gpios gpio0 PA4 低有效, no-mmc
 *     uart2  调试串口 uart2m0_xfer, 1500000n8
 *
 * ⚠️ 未实机验证。
 */

/dts-v1/;

#include <dt-bindings/gpio/gpio.h>
#include <dt-bindings/pinctrl/rockchip.h>
#include "rk3588.dtsi"

/ {{
	model = "{model}";
	compatible = "{compatible}", "rockchip,rk3588";

	aliases {{
		mmc0 = &sdhci;
		mmc1 = &sdmmc;
		serial2 = &uart2;
	}};

	chosen {{
		stdout-path = "serial2:1500000n8";
	}};
}};

/* 板载 eMMC（8 bit，不可插拔） */
&sdhci {{
	bus-width = <8>;
	no-sdio;
	no-sd;
	non-removable;
	max-frequency = <150000000>;
	mmc-hs200-1_8v;
	status = "okay";
}};

/* TF 卡槽（4 bit，卡检测 gpio0 PA4 低有效） */
&sdmmc {{
	bus-width = <4>;
	cap-mmc-highspeed;
	cap-sd-highspeed;
	cd-gpios = <&gpio0 RK_PA4 GPIO_ACTIVE_LOW>;
	disable-wp;
	no-mmc;
	no-sdio;
	sd-uhs-sdr104;
	status = "okay";
}};

/* 调试串口 */
&uart2 {{
	pinctrl-names = "default";
	pinctrl-0 = <&uart2m0_xfer>;
	status = "okay";
}};

/* ============================================================
 * 板载千兆网口：RTL8211F 走 GMAC0（板子只引出一个千兆口）
 *   reset = GPIO4_B3 低有效（厂商/armbian/leux 三方一致）
 * ============================================================ */
&gmac0 {{
	clock_in_out = "output";
	phy-mode = "{gm_phymode}";
	{delay_props}
	snps,reset-gpio = <&gpio4 RK_PB3 GPIO_ACTIVE_LOW>;
	snps,reset-active-low;
	snps,reset-delays-us = <0 20000 100000>;

	phy-handle = <&rgmii_phy>;
	pinctrl-names = "default";
	pinctrl-0 = <&gmac0_miim>,
		    <&gmac0_tx_bus2>,
		    <&gmac0_rx_bus2>,
		    <&gmac0_rgmii_clk>,
		    <&gmac0_rgmii_bus>;
	status = "okay";
}};

&mdio0 {{
	rgmii_phy: ethernet-phy@1 {{
		compatible = "ethernet-phy-ieee802.3-c22";
		reg = <0x1>;
	}};
}};

/* gmac1 板子没引出 */
&gmac1 {{
	status = "disabled";
}};

/* ============================================================
 * 两个 2.5G RTL8125 走 PCIe（参考 leux 的 H88K U-Boot 适配笔记）
 *   pcie2x1l1 ETH1 -> reset GPIO4_A2 高有效
 *   pcie2x1l2 ETH2 -> reset GPIO4_A5 高有效
 * ============================================================ */
&combphy1_ps {{
	status = "okay";
}};

&combphy2_psu {{
	status = "okay";
}};

&pcie2x1l1 {{
	reset-gpios = <&gpio4 RK_PA2 GPIO_ACTIVE_HIGH>;
	status = "okay";
}};
{eth2_node}
/* ============================================================
 * NVMe：M.2 M-Key 走 pcie3x4 + pcie30phy
 *   reset = GPIO4_B6 高有效
 * ============================================================ */
&pcie30phy {{
	status = "okay";
}};

&pcie3x4 {{
	reset-gpios = <&gpio4 RK_PB6 GPIO_ACTIVE_HIGH>;
	status = "okay";
}};
'''

OVERLAY = '''// SPDX-License-Identifier: (GPL-2.0+ OR MIT)
/*
 * {model} —— U-Boot overlay
 *
 * 把 eMMC / TF 卡节点标记为 pre-ram 可用，否则 SPL 阶段找不到启动介质。
 */

#include "rk3588-u-boot.dtsi"

&sdhci {{
	bootph-pre-ram;
	bootph-some-ram;
}};

&sdmmc {{
	bootph-pre-ram;
	bootph-some-ram;
}};
'''

DEFCONFIG = '''CONFIG_ARM=y
CONFIG_SKIP_LOWLEVEL_INIT=y
CONFIG_COUNTER_FREQUENCY=24000000
CONFIG_ARCH_ROCKCHIP=y
CONFIG_DEFAULT_DEVICE_TREE="rockchip/rk3588-hinlink-{board}"
CONFIG_ROCKCHIP_RK3588=y
CONFIG_ROCKCHIP_HANG_TO_BROM=y
CONFIG_SPL_SERIAL=y
# Conforms to upstream generic-rk3588: RK3588 needs a CONFIG_TARGET_*
# to pull in board support code, so we reuse the EVB target.
CONFIG_TARGET_EVB_RK3588=y
# NOTE: do NOT set "# CONFIG_OF_UPSTREAM is not set" (generic-rk3588 has it).
# With OF_UPSTREAM disabled u-boot looks for the board dts under arch/arm/dts/
# and requires it to be listed in arch/arm/dts/Makefile; enabling it (default)
# makes u-boot pick the dts from dts/upstream/src/arm64/rockchip/ automatically,
# which is where this file lives.
CONFIG_SYS_LOAD_ADDR=0xc00800
CONFIG_DEBUG_UART_BASE=0xFEB50000
CONFIG_DEBUG_UART_CLOCK=24000000
CONFIG_DEBUG_UART=y
CONFIG_FIT=y
CONFIG_FIT_VERBOSE=y
CONFIG_SPL_FIT_SIGNATURE=y
CONFIG_SPL_LOAD_FIT=y
# CONFIG_BOOTMETH_VBE is not set
CONFIG_LEGACY_IMAGE_FORMAT=y
CONFIG_OF_SYSTEM_SETUP=y
CONFIG_DEFAULT_FDT_FILE="rockchip/rk3588-hinlink-{board}.dtb"
# CONFIG_DISPLAY_CPUINFO is not set
CONFIG_SPL_MAX_SIZE=0x40000
# CONFIG_SPL_RAW_IMAGE_SUPPORT is not set
CONFIG_SPL_ATF=y
CONFIG_CMD_MEMINFO=y
CONFIG_CMD_MEMINFO_MAP=y
CONFIG_CMD_GPIO=y
CONFIG_CMD_GPT=y
CONFIG_CMD_MISC=y
CONFIG_CMD_MMC=y
CONFIG_CMD_ROCKUSB=y
CONFIG_CMD_USB_MASS_STORAGE=y
# CONFIG_CMD_SETEXPR is not set
CONFIG_CMD_RNG=y
# CONFIG_SPL_DOS_PARTITION is not set
CONFIG_SPL_OF_CONTROL=y
CONFIG_OF_LIVE=y
CONFIG_OF_SPL_REMOVE_PROPS="clock-names interrupt-parent assigned-clocks assigned-clock-rates assigned-clock-parents"
CONFIG_ENV_RELOC_GD_ENV_ADDR=y
# ---- 网络：板载 RTL8211F(GMAC0) + 2x RTL8125(PCIe) ----
# 注意：generic-rk3588_defconfig 原本有 CONFIG_NO_NET=y
# （它是无网口的通用板），本板有网口，必须去掉，否则网络驱动不编译。
CONFIG_PHYLIB=y
CONFIG_PHY_REALTEK=y
CONFIG_DWC_ETH_QOS=y
CONFIG_DWC_ETH_QOS_ROCKCHIP=y
CONFIG_DM_MDIO=y
# ---- PCIe：2 个 RTL8125 网卡 + M.2 NVMe ----
CONFIG_PCI=y
CONFIG_CMD_PCI=y
CONFIG_PCIE_DW_ROCKCHIP=y
CONFIG_RTL8169=y
CONFIG_CMD_NVME=y
CONFIG_NVME_PCI=y
CONFIG_SPL_DM_SEQ_ALIAS=y
CONFIG_SPL_SYSCON=y
# CONFIG_ADC is not set
CONFIG_SPL_CLK=y
# CONFIG_USB_FUNCTION_FASTBOOT is not set
CONFIG_ROCKCHIP_GPIO=y
CONFIG_MISC=y
CONFIG_SUPPORT_EMMC_RPMB=y
CONFIG_MMC_DW=y
CONFIG_MMC_DW_ROCKCHIP=y
CONFIG_MMC_SDHCI=y
CONFIG_MMC_SDHCI_SDMA=y
CONFIG_MMC_SDHCI_ROCKCHIP=y
CONFIG_PHY_ROCKCHIP_INNO_USB2=y
CONFIG_SPL_PINCTRL=y
CONFIG_SPL_RAM=y
CONFIG_BAUDRATE=1500000
CONFIG_DEBUG_UART_SHIFT=2
CONFIG_SYS_NS16550_MEM32=y
CONFIG_SYSRESET=y
CONFIG_SYSRESET_PSCI=y
CONFIG_USB=y
CONFIG_USB_DWC3=y
CONFIG_USB_DWC3_GENERIC=y
CONFIG_USB_GADGET=y
CONFIG_USB_GADGET_DOWNLOAD=y
CONFIG_USB_FUNCTION_ROCKUSB=y
CONFIG_ERRNO_STR=y
'''

ETH2_PCIE = (
    '&combphy0_ps {\n'
    '\tstatus = "okay";\n'
    '};\n'
    '\n'
    '&pcie2x1l2 {\n'
    '\treset-gpios = <&gpio4 RK_PA5 GPIO_ACTIVE_HIGH>;\n'
    '\tstatus = "okay";\n'
    '};\n')

BOARDS = [
    dict(board='h88k-v2', model='HINLINK OPC-H88K V2',
         compatible='hinlink,h88k-v2',
         # H88K v2 的 combphy0_ps 给了 SATA 座（见 108/109 的说明），
         # 所以它只有 2 个网口，u-boot 侧也不使能 pcie2x1l2。
         gm_phymode='rgmii-rxid',
         delay_props='tx_delay = <0x44>;',
         eth2_node='/* v2 的 combphy0_ps 给了 SATA 座 -> 没有第三个 2.5G 口 */\n'),
    dict(board='h88k-v3', model='HINLINK OPC-H88K V3',
         compatible='hinlink,h88k-v3',
         gm_phymode='rgmii-rxid',
         delay_props='tx_delay = <0x44>;',
         eth2_node=ETH2_PCIE),
    dict(board='h89k', model='HINLINK OPC-H89K',
         compatible='hinlink,h89k',
         # H89K 的 gmac0 厂商值是 rgmii + tx/rx delay 都显式给
         gm_phymode='rgmii',
         delay_props='tx_delay = <0x42>;\n\trx_delay = <0x34>;',
         eth2_node=ETH2_PCIE),
]


def new_file(path, content):
    n = content.count('\n')
    body = ''.join('+' + ln + '\n' for ln in content.split('\n')[:n])
    return ('--- /dev/null\n'
            '+++ b/%s\n'
            '@@ -0,0 +1,%d @@\n%s' % (path, n, body))


def main():
    parts = []
    for b in BOARDS:
        parts.append(new_file(
            'dts/upstream/src/arm64/rockchip/rk3588-hinlink-%s.dts' % b['board'],
            DTS.format(**b)))
        parts.append(new_file(
            'arch/arm/dts/rk3588-hinlink-%s-u-boot.dtsi' % b['board'],
            OVERLAY.format(**b)))
        parts.append(new_file(
            'configs/hinlink-%s-rk3588_defconfig' % b['board'],
            DEFCONFIG.format(**b)))

    header = '''From: HinLink adaptation for immortalwrt
Subject: [PATCH] board: rockchip: add HINLINK H88K / H89K u-boot support

上游 openwrt 只为 HINLINK 的 H28K / H66K / H68K 提供了 u-boot；本仓库的
RK3588 三款（OPC-H88K V2 / V3、OPC-H89K）在 u-boot 里既没有板级 dts，
也没有 rk806 dtsi，此前只能把 BOOT_FLOW 留空。

本 patch 为其补齐：

  dts/upstream/src/arm64/rockchip/rk3588-hinlink-{h88k-v2,h88k-v3,h89k}.dts
  arch/arm/dts/rk3588-hinlink-{h88k-v2,h88k-v3,h89k}-u-boot.dtsi
  configs/hinlink-{h88k-v2,h88k-v3,h89k}-rk3588_defconfig

设计取舍
--------
1. **不含 rk806 PMIC 节点**。RK3588 的 PMIC 由 Rockchip TPL
   (rk3588_ddr_lp4_2112MHz_lp5_2400MHz_v1.19.bin) 在 SPL 之前初始化
   （DDR 需要电压），U-Boot proper 不必再配一遍。少写这 34 路 regulator
   反而更安全 —— 抄错电压会把板子拉坏。代价是 U-Boot 下读不到 PMIC。
2. dts 只保留 eMMC / TF 卡 / 调试串口 —— U-Boot 阶段够用。
3. defconfig 基于 u-boot 自带的 generic-rk3588_defconfig；
   target 沿用 CONFIG_TARGET_EVB_RK3588（与上游 generic-rk3588 一致，
   RK3588 需要一个 CONFIG_TARGET_* 提供板级支持代码）。

存储与串口依据（厂商 dtb vendor-h89k.dtb 与现代 rk3588-hinlink.dtsi 两侧一致）
    sdhci  eMMC   bus-width 8, non-removable, mmc-hs200-1_8v
    sdmmc  TF 卡  bus-width 4, cd-gpios gpio0 PA4 低有效, no-mmc
    uart2  调试串口 uart2m0_xfer, 1500000n8

⚠️ 未实机验证。

Signed-off-by: HinLink immortalwrt adaptation
---
'''
    io.open(PATCH, 'w', encoding='utf-8', newline='\n').write(
        header + ''.join(parts))
    print('已生成 %s（%d 个新文件）' % (PATCH, len(parts)))


if __name__ == '__main__':
    main()
