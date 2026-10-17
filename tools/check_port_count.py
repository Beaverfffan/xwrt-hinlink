#!/usr/bin/env python3
"""机型口数自检：交叉校验 DTS 的网口构成 与 02_network 的接口映射。

背景
----
RK3568 板上有两类网口控制器：
  - GMAC（SoC 内部，枚举顺序固定）-> gmac0=eth0、gmac1=eth1
  - PCIe 2.5G（PCI 设备，枚举顺序随硬件变）-> rtl8125_1=eth2、rtl8125_2=eth3

机器的口数 = okay 的 GMAC 数 + okay 的 PCIe 控制器数。
02_network 里的 LAN+WAN 接口数必须与口数一致，否则少一个口的机器会配错。

★ 关键：DTS 通常不显式覆写 pcie3x1/pcie3x2，继承 rk3568-hinlink-opc.dtsi
  （dtsi 里两者都是 status="okay"）。所以必须把 dtsi 作为基线合并计算，
  只扫 DTS 会把四网口机误判成两网口。

用法：python3 tools/check_port_count.py <仓库根目录>
退出码：不一致时 1，一致时 0
"""
import re
import sys
import os
import glob
import io

root = sys.argv[1] if len(sys.argv) > 1 else '.'
DTS = os.path.join(root, 'target/linux/rockchip/files/arch/arm64/boot/dts/rockchip')
NET = os.path.join(root, 'target/linux/rockchip/armv8/base-files/etc/board.d/02_network')
DTSI = os.path.join(DTS, 'rk3568-hinlink-opc.dtsi')

# 期望口数（人工确认的硬件事实）。改 DTS 时必须同步改这里。
EXPECT = {
    # ---- RK3568 ----
    'rk3568-hinlink-h66k':        2,  # 无板载 GMAC，2xRTL8125（PCIe 枚举）
    # ★ 2026-10-12 改名+合并：机型名 = 世代板本串
    'rk3568-hinlink-h68k-a-b':     2,  # 2022 双千兆，2xGMAC，无 PCIe（SATA）
    'rk3568-hinlink-h68k-a-b-usb': 2,  # 同上，USB3.0
    'rk3568-hinlink-h68k-c-d-f':   4,  # 2xGMAC + 2xRTL8125（SATA）
    'rk3568-hinlink-h68k-c-d-f-usb': 4,  # 同上，USB3.0
    'rk3568-hinlink-h68k-new':    4,
    'rk3568-hinlink-h69k-3eth':   3,  # 屏蔽 gmac0 -> 1xGMAC(gmac1) + 2xRTL8125
    'rk3568-hinlink-h69k-mini':   4,  # = H68K max，2xGMAC + 2xRTL8125
    # ---- RK3528 ----
    # H28K 是**双网口**：eth0 = 板载 RTL8211F RGMII(gmac1)，
    # eth1 = PCIe RTL8111H（PCI 枚举产生，DT 里不写 pcie-eth）。
    # 依据 HinLink 官网产品页「网口2 RTL8111H PCIe 千兆」。
    'rk3528-hinlink-h28k':        2,
    # H29K 全系与 HT2 是**单网口**：只有板载 RGMII(gmac1)。
    # 厂商 h28x 固件里的 ht2 dtb（compatible = "hinlink,ht2"）同样只有
    # 一个 gmac，与本仓库一致。
    # ⚠️ 这两款 DTS 里**没有 &pcie 节点**，所以统计时 pcie 不计入，
    #    校验器天然算出 1 口 —— 不需要 EXCLUDE。
    'rk3528-hinlink-h29k-v1.3-1.14': 1,
    'rk3528-hinlink-h29k-v5-1.14':   1,
    'rk3528-hinlink-h29k-v5-1.49':   1,
    'rk3528-hinlink-h29k':        1,  # lede 参考版（无设备定义，仅校验不崩溃）
    'rk3528-hinlink-ht2':         1,
    # ---- RK3588 ----
    # H88K v2/v3 的板载网口都是 gmac0 + pcie2x1l1 = 2 口；
    # pcie3x4 是 PCIe x4 插槽位（v3 上跑 M.2 NVMe），不算板载网口。
    # v3 额外在 pcie2x1l2 挂了第三颗 RTL8125 ⇒ 3 口。
    'rk3588-hinlink-h88k-v2':     2,
    'rk3588-hinlink-h88k-v3':     3,
    'rk3588-hinlink-h89k':        3,  # 1xGMAC + 2xRTL8125，屏蔽 gmac1
}

# 只读这些节点
# 各 SoC 的网口控制器 label（RK3568 / RK3528 / RK3588 命名不同）
PORTS = {
    'rk3568': ('gmac0', 'gmac1', 'pcie3x1', 'pcie3x2'),
    'rk3528': ('gmac1', 'pcie'),
    # H88K 的两路 2.5G 挂在 pcie3x4(rtl8125) 与 pcie2x1l1(rtl8125)，
    # 由 rk3588-hinlink.dtsi 使能；pcie2x1l0 是 WiFi 不算网口。
    # H89K 则改用 pcie2x1l1 / pcie2x1l2。
    'rk3588': ('gmac0', 'gmac1', 'pcie2x1l1', 'pcie2x1l2', 'pcie3x4'),
}

# 各 SoC 用哪个 dtsi 作基线。RK3528 用内核自带 rk3528.dtsi（本仓库没有），
# 且该文件里 gmac0/gmac1 都是 status="disabled"，故传 None 走纯 DTS 判定。
DTSI_FOR = {
    'rk3568': 'rk3568-hinlink-opc.dtsi',
    'rk3528': None,
    'rk3588': 'rk3588-hinlink.dtsi',
}


def node_status(text, node):
    """返回 DTS/DTSI 中某节点的 status；节点不存在返回 None。

    ★ 没有 status 属性时返回 None（未知），**不能**默认当成 okay：
      RK3528 内核 rk3528.dtsi 里 gmac0/gmac1 都是 status = "disabled"，
      若把「未写 status」误判为 okay，H28K 会被算成 3 口（凭空多一个 gmac0）。
    """
    m = re.search(r'(?:^|\n)&?' + re.escape(node) + r' \{(.*?)\n\t\};',
                  text, re.S)
    if not m:
        return None
    s = re.search(r'status = "(\w+)"', m.group(1))
    # 节点存在但没写 status：按 SoC dtsi 的惯例视为未启用（disabled）
    return s.group(1) if s else 'disabled'


def dts_ports(dts, dtsi, soc='rk3568', exclude=()):
    """口数 = okay 的 GMAC + okay 的 PCIe 控制器。DTS 覆盖 dtsi。

    exclude：需要从统计中剔除的控制器名。
      用于「同一 SoC 上某个 PCIe 控制器在本机型上不是网口」的情况 ——
      例如 H89K 沿用 rk3588-hinlink.dtsi 基线时 pcie3x4 是 WiFi/SSD 位，
      而 H88K 上它才是 RTL8125。
    """
    n = 0
    for node in PORTS[soc]:
        if node in exclude:
            continue
        st = node_status(dts, node)
        if st is None and dtsi:
            st = node_status(dtsi, node)
        if st == 'okay':
            n += 1
    return n


# 按机型剔除的控制器（该控制器在本机型上确实不是板载网口）
EXCLUDE = {
    # H89K：pcie3x4 在 dtsi 里是 WiFi/SSD 位，H89K 的两路 2.5G 走
    # pcie2x1l1 / pcie2x1l2。不剔除会被算成 4 口。
    'rk3588-hinlink-h89k': ('pcie3x4',),
    # H88K v2：pcie3x4 是 **PCIe x4 插槽位**（上游 dtsi 注释：
    #   "H88K v1 & v2: pcie x4 slot"），用来插扩展网卡 / NVMe，
    #   不是板载网口。板载只有 gmac0 + pcie2x1l1 = 2 口。
    'rk3588-hinlink-h88k-v2': ('pcie3x4',),
    # H88K v3：同样剔除 pcie3x4（v3 上改跑 M.2 NVMe）；
    # 另外 gmac1 在 rk3588.dtsi 里默认 okay，但 H88K 只有 gmac0 板载 RGMII，
    # 不剔除会被算成 4 口。板载 = gmac0 + pcie2x1l1 + pcie2x1l2 = 3 口。
    'rk3588-hinlink-h88k-v3': ('pcie3x4', 'gmac1'),
}
# ⚠️ 不要再往 EXCLUDE 里加「PCIe 控制器没挂网卡节点」这种判断 ——
#   **DT 里没有网卡节点，不代表板上没有网卡。**
#   标准 PCI 设备（RTL8111H / RTL8125 等）靠内核 pcie 驱动枚举自动发现，
#   厂商 dtb 与上游 DTS 都不会写 pcie-eth。
#   H28K 就是活例子：官网写明有 PCIe 千兆口，厂商 dtb 全树无 pci10ec，
#   但 &pcie 是 okay + combphy 作 PCIe PHY ⇒ 网卡必然枚举出来。
#   所以口数只看「该机型有没有使能对应的 PCIe 控制器」。


def parse_net(path):
    """解析 board.d/02_network 的 case 标签 -> (LAN, WAN)。

    case 标签有两种形态：
      A) 标签在行首，含反斜杠续行：
           hinlink,opc-h68k-a|\\
           <TAB>hinlink,opc-h68k-a-sata|\\
           <TAB>linkstar,opc-h68k-a)
      B) 单行无续行：
           hinlink,opc-h69k)
    两种都要匹配上，且续行里的 compatible 不能漏。
    """
    text = io.open(path, encoding='utf-8').read()
    cases = {}

    # 逐行扫出所有 case 标签，再在每个分支内部找 ucidef。
    #
    # 为什么逐行而不是一条大正则：
    #  1) case 体里允许夹注释、夹别的命令（MAC 生成段就只做 MAC）；
    #  2) 续行缩进有两种 —— 接口映射段是 TAB，MAC 段是顶格；
    #  3) 用贪婪正则匹配「标签 + 续行」时会把**上一段**的收尾行
    #     连同一大串标签吞进同一个 group，导致前面的分支整个消失。
    #     逐行累积不会有这个问题。
    lines = text.splitlines()
    # 标签行的形态：兼容串本体，可带结尾 ')'（单标签）或 '|\'（续行）
    label_re = re.compile(r'^[a-z0-9][a-z0-9,\-]*(\)|\|\\?)?$')
    # marks[i] = (起止行号, [该分支的 compatible 列表])
    marks = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i].strip()
        if not label_re.match(ln):
            i += 1
            continue
        # 收集本分支的标签（含 | 续行）
        labels = []
        cur = ln
        while True:
            if cur.endswith('|\\') or cur.endswith('|'):
                labels.append(cur[:-2].strip() if cur.endswith('|\\') else cur[:-1].strip())
                i += 1
                if i >= n:
                    break
                cur = lines[i].strip()
                continue
            if cur.endswith(')'):
                labels.append(cur[:-1].strip())
                break
            # 不是合法 case 标签 —— 放弃这一段
            labels = []
            break
        if labels:
            marks.append((i, labels))
        i += 1

    # marks[i] 的分支体 = 第 marks[i][0]+1 行 .. 第 marks[i+1][0] 行
    for k, (endline, labels) in enumerate(marks):
        startline = endline + 1
        stopline = marks[k + 1][0] if k + 1 < len(marks) else n
        chunk = '\n'.join(lines[startline:stopline])
        u = re.search(r'ucidef_set_interfaces_lan_wan \'([^\']*)\'(?: \'([^\']*)\')?',
                      chunk)
        if not u:
            # 该分支没有接口映射（如 MAC 生成段）。不丢弃标签 ——
            # 同一个 compatible 可能在这个 case 里只做 MAC，
            # 在另一个 case 里才做接口映射。先占位，后续分支再填。
            for cp in labels:
                if cp and cp not in cases:
                    cases[cp] = None
            continue
        lan = [x for x in u.group(1).split() if x]
        wan = [x for x in (u.group(2) or '').split() if x]
        for cp in labels:
            if cp and cases.get(cp) is None:
                cases[cp] = (lan, wan)
    return {k2: v for k2, v in cases.items() if v is not None}


def main():
    net = parse_net(NET)
    dtsi_cache = {}

    def get_dtsi(soc):
        if soc not in dtsi_cache:
            fn = DTSI_FOR.get(soc)
            if not fn:
                dtsi_cache[soc] = ''
            else:
                p = os.path.join(DTS, fn)
                dtsi_cache[soc] = io.open(p, encoding='utf-8').read()
        return dtsi_cache[soc]

    print('%-40s %7s %6s %8s  %s' % ('DTS', 'DTS口', '期望', '映射数', 'LAN / WAN'))
    print('-' * 100)

    bad = 0
    files = sorted(glob.glob(os.path.join(DTS, 'rk35*-hinlink-h*.dts')))
    if not files:
        print('未找到 DTS 文件，检查路径：%s' % DTS)
        return 1

    for fn in files:
        base = os.path.basename(fn)[:-4]
        text = io.open(fn, encoding='utf-8').read()
        m_compat = re.search(r'compatible\s*=\s*((?:"[^"]+"\s*,?\s*)+);', text)
        m_compat = m_compat.group(1) if m_compat else ''
        # compatible 可能有多个（厂商前缀 + SoC 兼容串），全部取出
        # 例：compatible = "hinlink,opc-h28k", "hinlink,h28k", "hlink,h28k", "rockchip,rk3528";
        # 校验映射时只要**任意一个**能在 02_network 里命中即算通过。
        cps = [c.strip() for c in re.findall(r'"([^"]+)"', m_compat) if c.strip()]
        cp = cps[0] if cps else '?'
        soc = 'rk3528' if 'rk3528' in base else ('rk3588' if 'rk3588' in base else 'rk3568')
        n = dts_ports(text, get_dtsi(soc), soc, EXCLUDE.get(base, ()))
        exp = EXPECT.get(base, '?')

        hit = None
        for c in cps:
            if c in net:
                hit = c
                break

        if hit:
            lan, wan = net[hit]
            m = len(lan) + len(wan)
            mapping = '%s / %s  [%s]' % (' '.join(lan), ' '.join(wan), hit)
        else:
            m = None
            mapping = '(02_network 无此 compatible: %s)' % ', '.join(cps)

        ok = True
        if exp != '?':
            if n != exp:
                ok = False
            if m is not None and m != exp:
                ok = False
        if m is None and exp != '?':
            ok = False

        if not ok:
            bad += 1
        print('%-40s %7d %6s %8s  %-34s %s' % (
            base, n, exp, m if m is not None else '-', mapping,
            'OK' if ok else '<<< 不一致'))

    print()
    print('DTS 机型数: %d    不一致: %d' % (len(files), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
