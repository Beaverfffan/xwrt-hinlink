#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 HinLink 适配层集成进 x-wrt 树（分支 26.10_b202610170051 及以后）。

与 immortalwrt 版（repo2/tools/integrate.py）的差异：

  1. x-wrt 的 board.d 里**已经**有 hinlink,h28k / h66k / h68k 条目（上游自带），
     直接插会撞车：case 先匹配者生效，而 h68k 上游写的是 WAN=eth1
     （那是新机 h68k-new 的口位），老机 a-b / c-d-f 会被配错。
     ⇒ 先把 base 里的 hinlink 分支**整段摘掉**，再插我们的。
  2. x-wrt 的 armv8.mk 里已经有 4 个 hinlink 设备定义
     （hinlink_h28k / hinlink_h6xk / hinlink_h66k / hinlink_h68k）
     ⇒ 一并摘掉，换成我们的 16 个（名字不同，不摘会得到重复 profile）。
  3. U-Boot：x-wrt 已有 106/107 补丁与 h28k / h66k / h68k 三个变体；我们只补
     h29k / ht2 / h88k-v2 / h88k-v3 / h89k 五个变体，并把已有三个的
     BUILD_DEVICES 改成本仓库的 device 名（上游写的是它自己的 device 名，
     不改就选不上 u-boot 包，从零编译会在 image 阶段报 bin 不存在）。
  4. 不再安装 03_hinlink-lan-ip —— 用户要求放弃 192.168.100.1 默认网段，
     沿用 x-wrt 自己的默认（192.168.15.1）。

用法（在构建机上）：
    python3 ~/xwrt-adapt/tools/integrate.py [--src ...] [--dst ...]

本脚本**幂等**：重复运行结果一致。
"""
import argparse
import glob
import io
import os
import re
import shutil
import sys

HINLINK_PAT = re.compile(r'^[ \t]*(hinlink|hlink|linkstar),', re.M)
CASE_RE = re.compile(r'^[ \t]*case\s+"?\$board"?\s+in[ \t]*\n', re.M)
ESAC_RE = re.compile(r'^[ \t]*esac[ \t]*\n', re.M)
FALLBACK_RE = re.compile(r'^[ \t]*\*\)[ \t]*\n', re.M)


# --------------------------------------------------------------------------
def rd(p):
    return io.open(p, encoding="utf-8").read()


def wr(p, t):
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)


def blocks(text):
    """返回每个 `case "$board" in ... esac` 的 (body_start, body_end)。"""
    out, i = [], 0
    while True:
        m = CASE_RE.search(text, i)
        if not m:
            break
        bs = m.end()
        e = ESAC_RE.search(text, bs)
        if not e:
            break
        out.append((bs, e.start()))
        i = e.end()
    return out


# --------------------------------------------------------------------------
# 分支级裁剪：把 case 块里 hinlink 的分支整段摘掉
# --------------------------------------------------------------------------
def strip_hinlink(body):
    """摘掉 case 块里所有 hinlink 分支。

    ★ 必须连带摘掉**紧挨在分支上方的注释/空行**，否则脚本不幂等：
      我方插入的分支自带一大段注释，第二次运行时分支被摘掉、注释却留下，
      重插后注释越积越多。
    """
    lines = body.splitlines(True)
    out, pending = [], []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            pending.append(ln)
            i += 1
            continue
        # pattern 行：从 i 开始，直到某行以 `)` 结尾
        j = i
        pat = []
        while j < n:
            pat.append(lines[j])
            if lines[j].rstrip().endswith(")"):
                break
            j += 1
        if j >= n:                       # 不成形，原样输出
            out.extend(pending)
            out.extend(lines[i:])
            return "".join(out)
        # 分支体：到 `;;` 为止
        k, rest = j + 1, []
        while k < n:
            rest.append(lines[k])
            k += 1
            if lines[k - 1].strip() == ";;":
                break
        keep = [p for p in pat if not HINLINK_PAT.match(p)]
        if not keep:
            pending = []                 # 整段丢弃（连注释）
        elif len(keep) == len(pat):
            out.extend(pending)          # 与本机型无关，原样保留
            out.extend(pat + rest)
            pending = []
        else:
            out.extend(pending)
            pending = []
            fixed = [x if x.endswith("\n") else x + "\n" for x in keep]
            # 削短后最后一行仍须以 `)` 收口
            last = fixed[-1].rstrip("\n").rstrip()
            if not last.endswith(")"):
                if last.endswith("|\\"):
                    last = last[:-2].rstrip() + ")"
                elif last.endswith("|"):
                    last = last[:-1].rstrip() + ")"
                fixed[-1] = last + "\n"
            out.extend(fixed + rest)
        i = k
    out.extend(pending)
    return "".join(out)


def insert_point(body):
    """插到官方 `*)` 兜底**之前**；没有兜底就插到块末尾。"""
    m = FALLBACK_RE.search(body)
    return m.start() if m else len(body)


def merge_boardd(rock, src, name):
    base_p = os.path.join(rock, "armv8/base-files/etc/board.d", name)
    add_p = os.path.join(src, "target/linux/rockchip/armv8/base-files/etc/board.d", name)
    base, add = rd(base_p), rd(add_p)
    bb, ab = blocks(base), blocks(add)
    if not bb or not ab:
        print("  %-12s !! 找不到 case 块（base=%d add=%d），跳过" % (name, len(bb), len(ab)))
        return
    if len(bb) != len(ab):
        print("  %-12s !! case 块数不同 base=%d add=%d —— 跳过" % (name, len(bb), len(ab)))
        return

    had = len(HINLINK_PAT.findall(base))
    out = base
    for (bs, be) in reversed(bb):                       # 1) 摘上游 hinlink 分支
        out = out[:bs] + strip_hinlink(out[bs:be]) + out[be:]

    bb2 = blocks(out)
    for (bs, be), (as_, ae) in reversed(list(zip(bb2, ab))):   # 2) 倒序插我方分支
        body = add[as_:ae]
        body = re.sub(r'^[ \t]*\*\)[ \t]*\n(?:[ \t]*[^\n]*\n)*?[ \t]*;;[ \t]*\n',
                      '', body, flags=re.M)             # 我方兜底丢掉
        body = "\n" + body.lstrip("\n")                 # 分支前固定空一行
        pos = bs + insert_point(out[bs:be])
        out = out[:pos] + body + out[pos:]

    out = re.sub(r'\n{3,}', '\n\n', out)                # 收敛多余空行（幂等）
    wr(base_p, out)
    print("  %-12s 摘上游 %d 个 hinlink 分支，插入 %d 个 case 块" % (name, had, len(ab)))


# --------------------------------------------------------------------------
# armv8.mk：摘上游 hinlink 设备定义，挂我们的 include
# --------------------------------------------------------------------------
def strip_mk_devices(text):
    lines = text.splitlines(True)
    out, i, n, killed = [], 0, len(lines), []
    while i < n:
        if re.match(r'^define Device/hinlink', lines[i]):
            killed.append(lines[i].split()[1])
            j = i
            while j < n and lines[j].strip() != "endef":
                j += 1
            j += 1
            k = j
            while k < n and not lines[k].strip():
                k += 1
            if k < n and lines[k].startswith("TARGET_DEVICES += hinlink"):
                k += 1
            else:
                k = j
            i = k
            continue
        out.append(lines[i])
        i += 1
    return "".join(out), killed


def merge_image(rock, src):
    shutil.copy2(os.path.join(src, "target/linux/rockchip/image/armv8.mk.hinlink"),
                 os.path.join(rock, "image/armv8.mk.hinlink"))
    p = os.path.join(rock, "image/armv8.mk")
    t, killed = strip_mk_devices(rd(p))
    inc = "include ./armv8.mk.hinlink"
    if inc not in t:
        t = t.rstrip("\n") + "\n\n# HinLink 机型（外部维护，见 armv8.mk.hinlink）\n" + inc + "\n"
    wr(p, t)
    print("  armv8.mk：摘上游 %d 个 hinlink 设备 %s；include 已就位"
          % (len(killed), ",".join(killed) if killed else "(无)"))


# --------------------------------------------------------------------------
# U-Boot：对齐已有 3 个变体的 BUILD_DEVICES，补 5 个新变体
# --------------------------------------------------------------------------
UBOOT_NEW = [
    ("hinlink-h29k-rk3528", "rk3528", "HINLINK H29K",
     ["hinlink_h29k-v1.3-1.14_rk3528", "hinlink_h29k-v5-1.14_rk3528",
      "hinlink_h29k-v5-1.49_rk3528"]),
    ("hinlink-ht2-rk3528", "rk3528", "HINLINK OPC-HT2",
     ["hinlink_opc-ht2_rk3528"]),
    ("hinlink-h88k-v2-rk3588", "rk358x", "HINLINK H88K V2", ["hinlink_h88k_v2"]),
    ("hinlink-h88k-v3-rk3588", "rk358x", "HINLINK H88K V3", ["hinlink_h88k_v3"]),
    ("hinlink-h89k-rk3588", "rk358x", "HINLINK H89K", ["hinlink_opc-h89k_rk3588"]),
]

UBOOT_FIX = {
    "hinlink-h28k-rk3528": ("rk3528", "HINLINK H28K", ["hinlink_h28k_rk3528"]),
    "hinlink-h66k-rk3568": ("rk3568", "HINLINK H66K", ["hinlink_opc-h66k"]),
    "hinlink-h68k-rk3568": ("rk3568", "HINLINK H68K",
                            ["hinlink_opc-h68k-a-b", "hinlink_opc-h68k-a-b-usb",
                             "hinlink_opc-h68k-c-d-f", "hinlink_opc-h68k-c-d-f-usb",
                             "hinlink_opc-h68k-new", "hinlink_opc-h69k",
                             "hinlink_opc-h69k-mini"]),
}


def uboot_block(name, tpl, title, devs):
    s = "define U-Boot/%s\n  $(U-Boot/%s/Default)\n  NAME:=%s\n  BUILD_DEVICES:= \\\n" \
        % (name, tpl, title)
    s += "".join("    %s \\\n" % d for d in devs[:-1])
    s += "    %s\nendef\n" % devs[-1]        # 最后一项不带续行符
    return s


def edit_uboot(dst):
    p = os.path.join(dst, "package/boot/uboot-rockchip/Makefile")
    if not os.path.exists(p):
        print("  !! 找不到 uboot-rockchip/Makefile，跳过")
        return
    t = rd(p)

    # 1) 已有变体：整块重写（★ 不能只替换 BUILD_DEVICES 的那几行 ——
    #    上游最后一项**不带续行符**，用 `(?:    \S+ \\\n)+` 会一行都匹配不到，
    #    静默失败；2026-10-17 就是这样白跑了一轮）
    for name, (tpl, title, devs) in UBOOT_FIX.items():
        m = re.search(r'define U-Boot/%s\n(?:.*\n)*?endef\n' % re.escape(name), t)
        if not m:
            print("  !! 未找到 U-Boot/%s 的定义块" % name)
            continue
        new = uboot_block(name, tpl, title, devs)
        if t[m.start():m.end()] != new:
            t = t[:m.start()] + new + t[m.end():]

    anchor = "UBOOT_TARGETS := \\\n"
    if anchor not in t:
        print("  !! 找不到 UBOOT_TARGETS，跳过")
        return

    for name, tpl, title, devs in UBOOT_NEW:                # 2) 补新变体
        if ("define U-Boot/%s\n" % name) in t:
            continue
        i = t.index(anchor)
        t = t[:i] + uboot_block(name, tpl, title, devs) + "\n" + t[i:]

    for name, _tpl, _title, _devs in UBOOT_NEW:             # 3) UBOOT_TARGETS 补名字
        if re.search(r'^  %s \\$' % re.escape(name), t, re.M):
            continue
        t = t.replace(anchor, anchor + "  %s \\\n" % name, 1)

    wr(p, t)
    print("  uboot-rockchip/Makefile：3 个变体 BUILD_DEVICES 已对齐，补 %d 个变体"
          % len(UBOOT_NEW))
    # ★★ 必须清掉包元数据缓存，否则 tmp/.config-package.in 里还是旧的
    #    `default y if ... DEVICE_hinlink_h68k`（上游名），新的 device 名
    #    永远选不上 u-boot 包 ⇒ image 阶段报
    #      dd: failed to open '.../hinlink-h68k-rk3568-u-boot-rockchip.bin'
    #    然后 `make defconfig` 会按新 BUILD_DEVICES 自动选 u-boot 包。
    for c in ("tmp/.packageinfo", "tmp/.targetinfo",
              "tmp/.config-package.in", "tmp/.packagedeps"):
        f = os.path.join(dst, c)
        if os.path.exists(f):
            os.remove(f)
    print("  已清 tmp/.packageinfo / .targetinfo / .config-package.in / .packagedeps"
          "（必须随后重跑 make defconfig）")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/xwrt-adapt"))
    ap.add_argument("--dst", default=os.path.expanduser("~/xwrt-hinlink"))
    a = ap.parse_args()
    src = os.path.expanduser(a.src)
    dst = os.path.expanduser(a.dst)
    rock = os.path.join(dst, "target/linux/rockchip")
    if not os.path.isdir(rock):
        sys.exit("目标树不对：%s 不存在" % rock)

    print("[1] board.d 合并（先摘上游 hinlink 分支）")
    for n in ("01_leds", "02_network"):
        merge_boardd(rock, src, n)

    print("[2] 拷贝 DTS / dtsi")
    sd = os.path.join(src, "target/linux/rockchip/files/arch/arm64/boot/dts/rockchip")
    dd = os.path.join(rock, "files/arch/arm64/boot/dts/rockchip")
    os.makedirs(dd, exist_ok=True)
    cnt = 0
    for f in sorted(os.listdir(sd)):
        if not os.path.isfile(os.path.join(sd, f)) or f.startswith("vendor-"):
            continue
        shutil.copy2(os.path.join(sd, f), os.path.join(dd, f))
        cnt += 1
    print("  拷贝 %d 个文件" % cnt)

    print("[3] image 定义")
    merge_image(rock, src)

    print("[4] 内核 patch")
    pd = os.path.join(rock, "patches-6.18")
    os.makedirs(pd, exist_ok=True)
    # ★ 必须删掉上游这两个 hinlink 补丁：
    #   101 用 patch **新建** rk3528-hinlink-h28k.dts，而我们的同名文件来自
    #       files/，两套来源撞车 ⇒ 内核 prepare 阶段报
    #       "The next patch would create the file ... which already exists!
    #        Hunk #1 FAILED ... Patch failed!"
    #   121 改的是同一批 dts（加 led-* alias），这些 alias 我们**已经写进
    #       自己的 dts**，留着只会二次冲突。
    #   （101 顺带把 h28k dtb 登记进内核 dts Makefile —— 用不到：
    #     image.mk 的 Device/Build/dtb 是 cpp+dtc 直接编，不吃 dtb-y。）
    for pat in ("101-arm64-dts-rockchip-Add-HINLINK-H28K.patch",
                "121-arm64-dts-rockchip-add-led-aliases-for-HINLINK.patch"):
        p = os.path.join(pd, pat)
        if os.path.exists(p):
            os.remove(p)
            print("  - 删除上游 %s（与 files/ 里的同名 dts 冲突）" % pat)
    for f in sorted(glob.glob(os.path.join(src, "patches/*.patch"))):
        b = os.path.basename(f)
        shutil.copy2(f, os.path.join(pd, b))
        print("  + %s" % b)

    print("[5] 追加 target 内核 config")
    app_p = os.path.join(src, "target/linux/rockchip/hinlink-config.append")
    if os.path.exists(app_p):
        app = rd(app_p)
        strip_re = re.compile(r'\n*# =+ HinLink begin =+\n.*?# =+ HinLink end =+\n', re.S)
        done = []
        for f in sorted(glob.glob(os.path.join(rock, "armv8/config-*"))):
            t = rd(f)
            wr(f, strip_re.sub("\n", t).rstrip("\n") + "\n\n" + app)
            done.append(os.path.basename(f))
        print("  追加到 %s" % (", ".join(done) if done else "(未找到 config-*)"))
    else:
        print("  (无 hinlink-config.append，跳过)")

    print("[6] base-files 其它文件")
    bf_src = os.path.join(src, "target/linux/rockchip/armv8/base-files")
    bf_dst = os.path.join(rock, "armv8/base-files")
    EXEC_DIRS = ("init.d", "hotplug.d", "uci-defaults", "libexec")
    BOARD_D_MERGE = ("01_leds", "02_network")
    nfile = 0
    if os.path.isdir(bf_src):
        want, removed = set(), []
        for root, _, files in os.walk(bf_src):
            rel = os.path.relpath(root, bf_src)
            parts = [] if rel == "." else rel.split(os.sep)
            for f in files:
                if "board.d" in parts and f in BOARD_D_MERGE:
                    continue
                want.add(os.path.normpath(os.path.join(rel, f)))
        for root, _, files in os.walk(bf_dst):
            rel = os.path.relpath(root, bf_dst)
            for f in files:
                if not any(m in f.lower() for m in ("hinlink", "hlink")):
                    continue
                rp = os.path.normpath(os.path.join(rel, f)) if rel != "." else f
                if rp not in want:
                    os.remove(os.path.join(root, f))
                    removed.append(rp)
        if removed:
            print("  清理 %d 个已废弃文件：%s" % (len(removed), ", ".join(sorted(removed))))
        for root, _, files in os.walk(bf_src):
            rel = os.path.relpath(root, bf_src)
            parts = [] if rel == "." else rel.split(os.sep)
            od = bf_dst if rel == "." else os.path.join(bf_dst, rel)
            os.makedirs(od, exist_ok=True)
            for f in sorted(files):
                if "board.d" in parts and f in BOARD_D_MERGE:
                    continue
                dp = os.path.join(od, f)
                shutil.copy2(os.path.join(root, f), dp)
                if any(d in parts for d in EXEC_DIRS):
                    os.chmod(dp, 0o755)
                nfile += 1
        print("  拷贝 %d 个文件" % nfile)
    else:
        print("  (无 base-files 目录，跳过)")

    print("[7] package/beaverfffan")
    pkg_src = os.path.join(src, "package/beaverfffan")
    pkg_dst = os.path.join(dst, "package/beaverfffan")
    if os.path.isdir(pkg_src):
        if os.path.isdir(pkg_dst):
            shutil.rmtree(pkg_dst)
        shutil.copytree(pkg_src, pkg_dst)
        n = sum(len(fs) for _, _, fs in os.walk(pkg_dst))
        for d in sorted(os.listdir(pkg_dst)):
            print("  %s" % d)
        print("  同步 %d 个文件" % n)
    else:
        print("  (无 package/beaverfffan，跳过)")

    print("[8] U-Boot 补丁")
    pd = os.path.join(dst, "package/boot/uboot-rockchip/patches")
    if os.path.isdir(pd):
        have = set(os.listdir(pd))
        # 上游 106/107（H28K / H66K+H68K）：x-wrt 自带，只补缺的
        up = os.path.join(src, "patches-uboot/upstream")
        for f in sorted(glob.glob(os.path.join(up, "*.patch"))):
            b = os.path.basename(f)
            if b in have:
                print("  = %s（上游已有，跳过）" % b)
                continue
            shutil.copy2(f, os.path.join(pd, b))
            print("  + %s" % b)
        # 自建 120（H29K/HT2）/121（RK3588）：补上或覆盖
        for f in sorted(glob.glob(os.path.join(src, "patches-uboot/[0-9]*.patch"))):
            b = os.path.basename(f)
            shutil.copy2(f, os.path.join(pd, b))
            print("  + %s" % b)
    else:
        print("  !! 找不到 package/boot/uboot-rockchip/patches，跳过")

    print("[9] U-Boot 变体登记")
    edit_uboot(dst)

    print("\n集成完成。下一步：")
    print("  cd %s && cp configs/<机型>.config .config && make defconfig" % dst)


if __name__ == "__main__":
    main()
