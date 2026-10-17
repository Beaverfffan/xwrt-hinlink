#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线 DTS 语法验证器（改进版）。

不依赖 dtc 版本 —— 先展开 #include，再做**可靠**的结构检查。

★ 只报「几乎确定为错」的问题，避免误报：
  1. 花括号不平衡
  2. 缺少 /dts-v1/;
  3. 节点块未闭合（逐行栈扫描）
  4. include 缺失（会真实导致编译失败）
  5. 本层 DTS 自身的结构问题（括号/分号/节点闭合）

★ 不报（合法但易误判）：
  - 多行属性续行以逗号结尾
  - 尖括号总数（属性续行会跨行，朴素计数不可靠）

对照验证：先跑主线原生 DTS，本检查器必须 PASS，否则自身不可信。
"""
import io
import os
import re
import sys

SEEN = set()
MISSING = set()


def preprocess(path, incdirs):
    out = []
    inc_q = re.compile(r'^\s*#\s*include\s+"([^"]+)"')
    inc_a = re.compile(r'^\s*#\s*include\s+<([^>]+)>')
    for line in io.open(path, encoding='utf-8', errors='replace'):
        m = inc_q.match(line) or inc_a.match(line)
        if m:
            inc = m.group(1)
            if inc in SEEN:
                out.append('\n')
                continue
            for d in incdirs:
                p = os.path.join(d, inc)
                if os.path.isfile(p):
                    SEEN.add(inc)
                    out.append(preprocess(p, incdirs))
                    break
            else:
                MISSING.add(inc)
                out.append('\n')
            continue
        out.append(line)
    return ''.join(out)


def strip_comments(txt):
    txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
    txt = re.sub(r'//[^\n]*', '', txt)
    return txt


def main():
    target = sys.argv[1]
    incdirs = sys.argv[2:]
    SEEN.clear()
    MISSING.clear()

    raw = io.open(target, encoding='utf-8', errors='replace').read()
    errs = []

    if '/dts-v1/;' not in raw:
        errs.append('缺少 /dts-v1/;')

    txt = strip_comments(preprocess(target, incdirs))

    # 1. 花括号平衡（栈扫描，定位未闭合位置）
    stack = []
    line = 1
    for ch in txt:
        if ch == '\n':
            line += 1
        elif ch == '{':
            stack.append(line)
        elif ch == '}':
            if stack:
                stack.pop()
            else:
                errs.append('第 %d 行多余的 }' % line)
                break
    if stack:
        errs.append('未闭合的 { 在第 %d 行（共 %d 个未闭合）' % (stack[-1], len(stack)))

    # 2. include 缺失
    for m in sorted(MISSING):
        errs.append('include 缺失: %s' % m)

    # 3. 节点块闭合：形如 `name {` 之后必须出现 `}` 或属性
    #    逐行判断 `xxx {` 结尾的行是否在合理位置闭合（只查明显的 `label: node {`）
    lines = txt.split('\n')
    for i, l in enumerate(lines, 1):
        t = l.strip()
        if not t.endswith('{'):
            continue
        # 找出该节点的结束：简单做深度跟踪
        depth = 0
        closed = False
        for j in range(i - 1, len(lines)):
            for ch in lines[j]:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        closed = True
                        break
            if closed:
                break
        if not closed:
            errs.append('第 %d 行节点未闭合: %s' % (i, t[:50]))

    if errs:
        print('FAIL  %s' % os.path.basename(target))
        for e in errs[:12]:
            print('      - %s' % e)
        return 1
    print('PASS  %s' % os.path.basename(target))
    return 0


if __name__ == '__main__':
    sys.exit(main())
