#!/usr/bin/env python3
"""DTS phandle 交叉引用校验。

为什么需要它
------------
`dts_syntax_check.py` 只查括号平衡与 include 完整性，**不查 phandle**。
而 DTS 里最常见的编译失败恰恰是 `&xxx` 引用了一个不存在的标签 ——
6.18 把RK3568 的 SoC 节点拆到 `rk356x-base.dtsi` 后，很多旧标签
（如 `rk809_grf`）消失了，本仓库 5 份 DTS 一直带着这个失效引用。

本工具做静态的标签解析：
  1. 收集内核 rockchip 目录所有 dts/dtsi 里定义的标签（含 `xxx: name {`）
  2. 收集 `dt-bindings/*` 里的 C 宏（`pcfg_*` 等，它们以 `#define` 出现）
  3. 收集本仓库 DTS 自己定义的标签
  4. 逐份 DTS 找出 `&label` 中无法解析的引用

它**不能**替代 dtc（不验证 reg/中断号等），但足以抓住 label 缺失
这类最常见的编译阻塞。

用法
----
  python3 tools/check_phandle.py <仓库根目录> <内核目录>

  <内核目录> 形如 /path/to/linux-6.18，其下必须有
             arch/arm64/boot/dts/rockchip/

退出码：全部可解析 0，有无法解析的引用 1。
"""
import re
import io
import os
import sys
import glob

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
KERNEL = sys.argv[2] if len(sys.argv) > 2 else ''
DTS = os.path.join(ROOT, 'target/linux/rockchip/files/arch/arm64/boot/dts/rockchip')

# DTS 里合法的"伪引用"，不是真label
PSEUDO = {
    '{/}',           # &{/} { ... }  —— 往已有节点追加属性
}

LABEL_DEF = re.compile(r'^\s+([A-Za-z_][\w,\-]*):\s*[^\s]', re.M)
LABEL_DEF2 = re.compile(r'^\s+([A-Za-z_][\w,\-]*):\s', re.M)
MACRO_DEF = re.compile(r'^\s*#define\s+(pcfg_\w+)', re.M)
REF = re.compile(r'&([A-Za-z_][\w]*)')


def strip_comments(text):
    """去掉 /* */ 与 // 注释，避免注释里提到的 &label 造成误报。

    ★ 必须做 —— 本仓库的 DTS 注释里会写「原来写的 &gpio5 是错的」这类
    说明，若不剥离就会把注释里的失效标签当成真引用。
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = (j + 2) if j >= 0 else n
        elif text.startswith('//', i):
            j = text.find('\n', i)
            i = j if j >= 0 else n
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def collect_kernel_labels(kdir):
    """收集内核 rockchip dts/dtsi 里定义的全部标签 + pcfg 宏。"""
    base = os.path.join(kdir, 'arch', 'arm64', 'boot', 'dts', 'rockchip')
    if not os.path.isdir(base):
        return None, None
    labels = set()
    macros = set()
    for f in glob.glob(os.path.join(base, '*.dts')) + glob.glob(os.path.join(base, '*.dtsi')):
        try:
            t = io.open(f, encoding='utf-8', errors='ignore').read()
        except IOError:
            continue
        labels |= set(LABEL_DEF.findall(t))
        labels |= set(LABEL_DEF2.findall(t))
        macros |= set(MACRO_DEF.findall(t))
    return labels, macros


def main():
    files = sorted(glob.glob(os.path.join(DTS, 'rk35*.dts')))
    if not files:
        print('未找到 DTS：%s' % DTS)
        return 1

    klabels, kmacros = (set(), set())
    if KERNEL and os.path.isdir(KERNEL):
        klabels, kmacros = collect_kernel_labels(KERNEL)
        print('内核标签 %d 个，pcfg 宏 %d 个（来自 %s）'
              % (len(klabels), len(kmacros), KERNEL))
    else:
        print('⚠️  未提供内核目录 —— 只能校验本仓库内引用，无法发现缺失的 SoC 标签')
        print('    用法：python3 tools/check_phandle.py <仓库根> <内核源码目录>')

    print('扫描 %d 份 DTS' % len(files))
    print('-' * 78)

    bad = 0
    for fn in files:
        base = os.path.basename(fn)
        raw = io.open(fn, encoding='utf-8').read()
        t = strip_comments(raw)   # ★ 剥离注释，避免假引用
        # 本文件里定义的标签
        own = set(LABEL_DEF.findall(t)) | set(LABEL_DEF2.findall(t))
        refs = set(REF.findall(t))
        miss = []
        for r in sorted(refs):
            if r in PSEUDO:
                continue
            if r in own or r in klabels or r in kmacros:
                continue
            miss.append(r)
        # 文件自己的 include 链里可能还有 opc.dtsi 等，也算本地标签
        if miss:
            # 再查同目录的 dtsi（opc.dtsi 里的标签也算）
            for other in glob.glob(os.path.join(DTS, '*.dtsi')):
                ot = io.open(other, encoding='utf-8', errors='ignore').read()
                olabels = set(LABEL_DEF.findall(ot)) | set(LABEL_DEF2.findall(ot))
                omacros = set(MACRO_DEF.findall(ot))
                still = [x for x in miss
                         if x not in olabels and x not in omacros]
                if still == miss:
                    break
                miss = still
        if miss:
            bad += 1
            print('❌ %-36s 无法解析: %s' % (base, ', '.join(miss)))
        else:
            print('✅ %-36s (%d 个引用全部可解析)' % (base, len(refs)))

    print('-' * 78)
    print('结果：%d 份 OK，%d 份有无法解析的引用' % (len(files) - bad, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
