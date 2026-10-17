#!/usr/bin/env python3
"""校验合并后的 board.d：我们的机型必须落在官方 `*)` 兜底之前，否则永不执行。"""
import io, re, sys, os

MINE = ("hinlink,opc-", "hinlink,h28k", "hinlink,h29k", "hlink,h28k",
        "linkstar,", "hinlink,h66k", "hinlink,h68k", "hinlink,h88k",
        "hinlink,h89k", "hinlink,ht2", "hlink,ht2")

def scan(fn):
    t = io.open(fn, encoding="utf-8").read()
    print("=" * 78)
    print(fn)
    n = 0
    for m in re.finditer(r'case\s+"?\$board"?\s+in\n', t):
        n += 1
        s = m.end()
        em = re.search(r'^[ \t]*esac\n', t[s:], re.M)
        if not em:
            print("  块%d: 找不到 esac!" % n); continue
        e = s + em.start()
        body = t[s:e]
        star = re.search(r'^[ \t]*\*\)', body, re.M)
        spos = star.start() if star else len(body)
        before = body[:spos]
        after = body[spos:]
        cnt_b = sum(before.count(k) for k in MINE)
        cnt_a = sum(after.count(k) for k in MINE)
        print("  块%d (第 %d 行起): 我们的条目 兜底前=%d 兜底后=%d %s"
              % (n, t[:m.start()].count("\n") + 1, cnt_b, cnt_a,
                 "✅" if cnt_a == 0 else "❌ 有分支会被 *) 吞掉"))
        if cnt_a:
            for ln in after.splitlines():
                if any(k in ln for k in MINE):
                    print("      会被吞: %s" % ln.strip())
    if n == 0:
        print("  ❌ 没有 case 块")

for f in sys.argv[1:]:
    scan(f)
