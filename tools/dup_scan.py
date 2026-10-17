#!/usr/bin/env python3
"""机型去重扫描：找出硬件配置实质相同的 DTS。

为什么要做
----------
HinLink 的同一块板子常被起多个文件名（改型、批次年份、厂商内部命名），
导致仓库里出现多份 DTS，但它们的**硬件配置部分完全一样**，
只有 model / compatible 字符串不同 —— 这对用户毫无价值，只是维护负担。

★ 合并历史
--------------------------------------
2026-10-09：`h68k-c-usb` 与 `h68k-c-usb3` 合并（硬件配置完全相同）。
2026-10-09：`h68k-c` 与 `h68k-d`、`h68k-c-usb3` 与 `h68k-d-usb` 当时记的理由是
            「02_network 的 WAN 口位置不同」，故未合并 —— **该理由已于
            2026-10-12 被实机推翻**（h68k-c 的 WAN 实际就是 eth0，两组映射一致）。
2026-10-12：上述两组**实际合并**，并按用户要求改成世代板本名：

    rk3568-hinlink-h68k-a-b.dts         ← 原 h68k-a.dts（SATA）
    rk3568-hinlink-h68k-a-b-usb.dts     ← 原 h68k-a-usb.dts（USB3.0）
    rk3568-hinlink-h68k-c-d-f.dts       ← 原 h68k-c.dts + h68k-d.dts
    rk3568-hinlink-h68k-c-d-f-usb.dts   ← 原 h68k-c-usb3.dts + h68k-d-usb.dts

    ⇒ a/a-usb **不能**合并：只差 `&sata0 { status }` 一行，而 sata0 与 USB3.0
      在 RK3568 上争同一颗 combphy0，硬件二选一。
    ⇒ 因此 `KEEP_SEPARATE` 现为空集（保留机制备用）。

⇒ 本工具扫出重复后，**必须再查 02_network 的接口映射**才能决定是否合并。
   映射一致 → 可合并；映射不同 → 不能合并。

判定方法
--------
把 DTS 归一化后两两比较：
  1. 去掉全部注释（/* */ 与 //）
  2. 归一 model / compatible 字符串（它们本来就该不同）
  3. 归一空白
  4. 比较剩余的「硬件配置指纹」

指纹相同 ⇒ 硬件配置一致 ⇒ 重复候选。
工具会同时打印两者的 02_network 映射，供人工判断。

用法
----
python3 tools/dup_scan.py [仓库根目录]
"""
import re
import sys
import os
import glob
import io
import itertools

root = sys.argv[1] if len(sys.argv) > 1 else '.'
DTS = os.path.join(root, 'target/linux/rockchip/files/arch/arm64/boot/dts/rockchip')


def strip_comments(text):
    """去掉 /* */ 与 // 注释，保留字符串内容。"""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = text.find('"', i + 1)
            if j < 0:
                j = n - 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = (j + 2) if j >= 0 else n
        elif text.startswith('//', i):
            j = text.find('\n', i)
            i = j if j >= 0 else n
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def normalize(text):
    """归一化成硬件配置指纹。"""
    t = strip_comments(text)
    # model / compatible 的字符串内容不参与指纹（本来就该不同）
    t = re.sub(r'model\s*=\s*"[^"]*"\s*;', 'model = "X";', t)
    t = re.sub(r'compatible\s*=\s*[^;]+;', 'compatible = "X";', t)
    # 连续空白压成一个空格
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


NET = os.path.join(root, 'target/linux/rockchip/armv8/base-files/etc/board.d/02_network')

# 已人工确认「不合并」的例外。
# 2026-10-12：h68k-c/d 与 c-usb3/d-usb **已实际合并**（DTS 与映射都一致），
# 所以这里现在是空的。保留该机制，供以后出现「内容相同但必须分开」的情况时登记。
KEEP_SEPARATE = set()


def parse_net(path):
    """解析 02_network：compatible -> (LAN, WAN)。

    逐行扫 case 标签（不用大正则，避免贪婪匹配跨分支吞掉整段），
    再在每个分支内找 ucidef_set_interfaces_lan_wan。
    """
    if not os.path.exists(path):
        return {}
    text = io.open(path, encoding='utf-8').read()
    lines = text.splitlines()
    label_re = re.compile(r'^[a-z0-9][a-z0-9,\-]*(\)|\|\\?)?$')
    marks = []
    i, n = 0, len(lines)
    while i < n:
        cur = lines[i].strip()
        if not label_re.match(cur):
            i += 1
            continue
        labels = []
        while True:
            if cur.endswith('|\\'):
                labels.append(cur[:-2].strip())
                i += 1
                if i >= n:
                    break
                cur = lines[i].strip()
                continue
            if cur.endswith('|'):
                labels.append(cur[:-1].strip())
                i += 1
                if i >= n:
                    break
                cur = lines[i].strip()
                continue
            if cur.endswith(')'):
                labels.append(cur[:-1].strip())
                break
            labels = []
            break
        if labels:
            marks.append((i, labels))
        i += 1

    cases = {}
    for k, (endline, labels) in enumerate(marks):
        stop = marks[k + 1][0] if k + 1 < len(marks) else n
        chunk = '\n'.join(lines[endline + 1:stop])
        u = re.search(r'ucidef_set_interfaces_lan_wan \'([^\']*)\'(?: \'([^\']*)\')?', chunk)
        if not u:
            for cp in labels:
                if cp and cp not in cases:
                    cases[cp] = None
            continue
        lan = tuple(u.group(1).split())
        wan = tuple((u.group(2) or '').split())
        for cp in labels:
            if cp and cases.get(cp) is None:
                cases[cp] = (lan, wan)
    return {k: v for k, v in cases.items() if v is not None}


def ident(fn):
    """取 DTS 的 compatible 首项与 model。"""
    t = io.open(fn, encoding='utf-8').read()
    cp = re.search(r'compatible\s*=\s*"([^"]+)"', t)
    md = re.search(r'model\s*=\s*"([^"]*)"', t)
    return (cp.group(1) if cp else '?', md.group(1) if md else '?')


def fmt_net(cp, net):
    if cp not in net:
        return '(02_network 无此compatible)'
    lan, wan = net[cp]
    return 'LAN=%-14s WAN=%s' % (' '.join(lan) or '—', ' '.join(wan) or '—')


def main():
    files = sorted(glob.glob(os.path.join(DTS, 'rk35*.dts')))
    if not files:
        print('未找到 DTS，检查路径：%s' % DTS)
        return 1

    net = parse_net(NET)
    fps = {}
    for fn in files:
        fps[os.path.basename(fn)] = normalize(
            io.open(fn, encoding='utf-8').read())

    dups = []
    for a, b in itertools.combinations(sorted(fps), 2):
        if fps[a] == fps[b]:
            dups.append((a, b))

    print('扫描 %d 份 DTS' % len(files))
    print('=' * 78)
    if not dups:
        print('未发现硬件配置完全相同的 DTS。')
        return 0

    print('发现 %d 组重复：\n' % len(dups))
    for a, b in dups:
        fa, fb = os.path.join(DTS, a), os.path.join(DTS, b)
        ica, mda = ident(fa)
        icb, mdb = ident(fb)
        na, nb = fmt_net(ica, net), fmt_net(icb, net)
        same = (na == nb) and not na.startswith('(02_network')

        if (a, b) in KEEP_SEPARATE:
            verdict = '⚠️  **刻意保留独立**（映射一致，但厂商按两个型号出货，保留型号名）'
        elif same:
            verdict = '✅ **可合并**（02_network 映射一致）'
        elif na.startswith('(02_network') or nb.startswith('(02_network'):
            verdict = '❓ 需人工确认（有一方在 02_network 里找不到）'
        else:
            verdict = '⚠️  需人工确认（02_network 映射不一致）'

        print('  %s   (%d B)' % (a, os.path.getsize(fa)))
        print('      compatible = %s' % ica)
        print('      model      = %s' % mda)
        print('      %s' % na)
        print('  %s   (%d B)' % (b, os.path.getsize(fb)))
        print('      compatible = %s' % icb)
        print('      model      = %s' % mdb)
        print('      %s' % nb)
        print('  => %s' % verdict)
        print('-' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
