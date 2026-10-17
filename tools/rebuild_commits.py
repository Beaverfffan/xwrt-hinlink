#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_commits.py —— 把 HinLink 适配按「基础设施 + 每机型一个提交」重放进 git。

背景
----
先前是一个 commit 把整批适配塞进去（单提交快照）—— 看不出哪个改动属于哪个
机型，也没法逐机型回溯。本脚本把同一份最终内容**重放**成一串提交：

    base（官方 immortalwrt 完整历史，HEAD 已 reset 到这里）
      └─ 基础设施：U-Boot / 内核 patch / 公共 dtsi / board.d 映射表 /
                    5G 复位应用 / package/beaverfffan / 文档
      └─ 机型 h66k        DTS + defconfig + 机型文档 + armv8.mk.hinlink 段
      └─ ...（顺序 = armv8.mk.hinlink 里 define Device 的出现顺序）

用法
    python3 rebuild_commits.py <SNAP> <TREE>
      SNAP = 含最终态的完整树快照（cp -a 出来的，带 .git）
      TREE = 目标仓库，HEAD 已 reset --hard 到官方提交、工作区 = 官方态

四个踩过的坑（都写在代码注释里了）
  1. 改动清单不能靠 `git status` —— SNAP 若是已提交状态，status 是干净的；
     正确基准是「SNAP 与 TREE（官方态）逐文件比对」。
  2. 读文件要能回退成 bytes，否则遇到 `.dtb` 这种二进制直接 UnicodeDecodeError。
  3. `armv8.mk.hinlink` 的段之间有空行，追加时**不能 rstrip**，否则差异。
  4. board.d 的两个映射表**不按机型拆**：我方分支在文件里是夹在官方分支之间的
     （多年多次插入的结果），没有统一规则能逐步重建 ⇒ 整份进基础设施提交。

结束时逐文件比对 TREE 与 SNAP（跳过 gitignore 覆盖的路径），
有任何不一致就报错退出 —— 宁可失败也不留错树。
"""
import io
import os
import re
import subprocess
import sys

SNAP = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/hinlink-snap")
TREE = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else "~/iwrt-hinlink-full")

MK = "target/linux/rockchip/image/armv8.mk.hinlink"
DTS_DIR = "target/linux/rockchip/files/arch/arm64/boot/dts/rockchip"
NET = "target/linux/rockchip/armv8/base-files/etc/board.d/02_network"
LED = "target/linux/rockchip/armv8/base-files/etc/board.d/01_leds"

# armv8.mk.hinlink 段名 → 机型（None = 公共段，归基础设施）
MK_MAP = {
    "hinlink_common": None,
    "hinlink_h6xk_base": None,
    "hinlink_h6xk_m2_wifi": None,
    "hinlink_h6xk_sdio_aic8800": None,
    "hinlink_h6xk_sdio_ap6256": None,
    "hinlink_opc-h66k": "h66k",
    "hinlink_opc-h68k-a-b": "h68k-a-b",
    "hinlink_opc-h68k-a-b-usb": "h68k-a-b-usb",
    "hinlink_opc-h68k-c-d-f": "h68k-c-d-f",
    "hinlink_opc-h68k-c-d-f-usb": "h68k-c-d-f-usb",
    "hinlink_opc-h68k-new": "h68k-new",
    "hinlink_opc-h69k": "h69k",
    "hinlink_opc-h69k-mini": "h69k-mini",
    "hinlink_h28k_rk3528": "h28k",
    "hinlink_h29k-v1.3-1.14_rk3528": "h29k-v1.3-1.14",
    "hinlink_h29k-v5-1.14_rk3528": "h29k-v5-1.14",
    "hinlink_h29k-v5-1.49_rk3528": "h29k-v5-1.49",
    "hinlink_opc-ht2_rk3528": "ht2",
    "hinlink_opc-h89k_rk3588": "h89k",
    "hinlink_h88k_v2": "h88k-v2",
    "hinlink_h88k_v3": "h88k-v3",
}

# DTS 文件 → 机型（None = 归基础设施，如 lede 的 h29k 参考存档）
DTS_MAP = {
    "rk3528-hinlink-h28k.dts": "h28k",
    "rk3528-hinlink-h29k-v1.3-1.14.dts": "h29k-v1.3-1.14",
    "rk3528-hinlink-h29k-v5-1.14.dts": "h29k-v5-1.14",
    "rk3528-hinlink-h29k-v5-1.49.dts": "h29k-v5-1.49",
    "rk3528-hinlink-ht2.dts": "ht2",
    "rk3528-hinlink-h29k.dts": None,          # lede 参考存档，不参与编译
    "rk3568-hinlink-h66k.dts": "h66k",
    "rk3568-hinlink-h68k-a-b-usb.dts": "h68k-a-b-usb",
    "rk3568-hinlink-h68k-a-b.dts": "h68k-a-b",
    "rk3568-hinlink-h68k-c-d-f-usb.dts": "h68k-c-d-f-usb",
    "rk3568-hinlink-h68k-c-d-f.dts": "h68k-c-d-f",
    "rk3568-hinlink-h68k-new.dts": "h68k-new",
    "rk3568-hinlink-h69k-3eth.dts": "h69k",
    "rk3568-hinlink-h69k-mini.dts": "h69k-mini",
    "rk3588-hinlink-h88k-v2.dts": "h88k-v2",
    "rk3588-hinlink-h88k-v3.dts": "h88k-v3",
    "rk3588-hinlink-h89k.dts": "h89k",
}


def rd(p):
    """读文件：UTF-8 解得开当文本，否则回退 bytes（树里有 .dtb 这类二进制）。"""
    raw = open(p, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw


def wr(p, t):
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    if isinstance(t, bytes):
        open(p, "wb").write(t)                                     # 二进制原样
    else:
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)    # 文本统一 LF


def git(*a):
    r = subprocess.run(["git"] + list(a), cwd=TREE, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode != 0:
        sys.exit("git %s 失败：\n%s" % (" ".join(a), r.stdout))
    return r.stdout


def ignored(rel):
    return subprocess.run(["git", "check-ignore", "-q", rel],
                          cwd=TREE).returncode == 0


def commit(msg, paths):
    paths = [p for p in dict.fromkeys(paths) if os.path.exists(os.path.join(TREE, p))]
    if not paths:
        return
    git("add", "-A", "--", *paths)
    if not git("diff", "--cached", "--name-only").strip():
        return
    git("-c", "user.name=Beaverfffan",
        "-c", "user.email=beaverfffan@users.noreply.github.com",
        "commit", "-q", "-m", msg)
    n = len(git("show", "--stat", "--format=", "HEAD").strip().splitlines()) - 1
    print("  ✔ %-40s %d 个文件" % (msg.split("（")[0][:40], n))


def split_mk(txt):
    """按 define Device/ 切段 → (文件头, [(段名, 段文本)])，段文本含尾随空行。"""
    pos = [m.start() for m in re.finditer(r'^define Device/', txt, re.M)]
    if not pos:
        return txt, []
    head = txt[:pos[0]]
    segs = []
    for i, a in enumerate(pos):
        b = pos[i + 1] if i + 1 < len(pos) else len(txt)
        seg = txt[a:b]
        segs.append((re.match(r'define Device/(\S+)', seg).group(1), seg))
    return head, segs


def main():
    if not os.path.isdir(os.path.join(SNAP, ".git")):
        sys.exit("SNAP 里没有 .git：%s" % SNAP)

    # ---- 1) 改动清单：SNAP vs TREE（跳过 gitignore 覆盖的路径）----
    files = []
    for root, dirs, fs in os.walk(SNAP):
        dirs[:] = [d for d in dirs
                   if d != ".git"
                   and not ignored(os.path.relpath(os.path.join(root, d), SNAP)
                                   .replace(os.sep, "/") + "/")]
        for f in fs:
            rel = os.path.relpath(os.path.join(root, f), SNAP).replace(os.sep, "/")
            if ignored(rel):
                continue
            a, b = os.path.join(SNAP, rel), os.path.join(TREE, rel)
            if not os.path.exists(b) or rd(a) != rd(b):
                files.append(rel)
    files.sort()
    print("相对官方态共 %d 个文件有差异" % len(files))

    # ---- 2) 分类 ----
    dev_files, infra = {}, []
    for rel in files:
        b = os.path.basename(rel)
        # ★ board.d 的两个映射表不按机型拆（见文件头说明）
        if rel in (NET, LED):
            infra.append(rel)
            continue
        s = None
        if rel.startswith("configs/") and b.endswith(".config"):
            s = b[:-len(".config")]
        elif rel.startswith("docs/devices/") and b.endswith(".md"):
            s = b[:-3]
        elif rel.startswith(DTS_DIR + "/") and b in DTS_MAP:
            s = DTS_MAP[b]
        if s:
            dev_files.setdefault(s, []).append(rel)
        else:
            infra.append(rel)

    # ---- 3) mk 段顺序 → 机型提交顺序 ----
    mk_head, mk_segs = split_mk(rd(os.path.join(SNAP, MK)))
    order_seq, seg_by_short, common_segs = [], {}, []
    for name, seg in mk_segs:
        owner = MK_MAP.get(name, "?")
        if owner is None:
            common_segs.append(seg)
            continue
        if owner == "?":
            print("  ⚠ 未知 mk 段：%s" % name)
            continue
        if owner not in order_seq:
            order_seq.append(owner)
        seg_by_short.setdefault(owner, []).append(seg)
    print("机型提交顺序：\n  " + " ".join(order_seq))
    orphan = sorted(set(dev_files) - set(order_seq))
    if orphan:
        print("  ⚠ 有文件但无 mk 段的机型：%s" % " ".join(orphan))

    # ---- 4) 基础设施 ----
    print("\n[0] 基础设施（%d 个文件）" % len(infra))
    for rel in infra:
        wr(os.path.join(TREE, rel), rd(os.path.join(SNAP, rel)))
    wr(os.path.join(TREE, MK), mk_head + "".join(common_segs))
    commit("rockchip: HinLink 适配基础\n\n"
           "U-Boot 板级支持（106~109 patch）、内核 patch（H29K 屏幕 / fbtft GC9307）、\n"
           "公共 dtsi（rk3568-hinlink-opc.dtsi、rk3588-hinlink.dtsi 等）、\n"
           "board.d 板级映射表（02_network / 01_leds / 03_hinlink-lan-ip）、\n"
           "5G 复位应用 luci-app-hinlink-modem-hardreset（包化）、\n"
           "package/beaverfffan（风扇温控 / SSD1306 / AIC8800）、\n"
           "每机型 defconfig 生成器 tools/gen_configs.py 与文档框架。\n\n"
           "board.d 的两张映射表含全部 16 机型的条目 —— 它是跨机型的共享表，\n"
           "不随单个机型提交。",
           list(infra) + [MK])

    # ---- 5) 逐机型 ----
    for seq, short in enumerate(order_seq):
        print("\n[%d/%d] %s" % (seq + 1, len(order_seq), short))
        paths = list(dev_files.get(short, []))
        for rel in paths:
            wr(os.path.join(TREE, rel), rd(os.path.join(SNAP, rel)))
        # ★ 直接追加，不能 rstrip（段文本自带尾随空行，压掉就与快照不一致）
        cur = rd(os.path.join(TREE, MK))
        for seg in seg_by_short.get(short, []):
            cur += seg
            paths.append(MK)
        wr(os.path.join(TREE, MK), cur)
        commit("rockchip: 新增机型 %s\n\n"
               "DTS + configs/%s.config + docs/devices/%s.md\n"
               "+ armv8.mk.hinlink 的 Device 定义" % (short, short, short),
               paths)

    # ---- 6) 校验 ----
    print("\n=== 校验 TREE 与 SNAP ===")
    bad = [rel for rel in files
           if not os.path.exists(os.path.join(TREE, rel))
           or rd(os.path.join(TREE, rel)) != rd(os.path.join(SNAP, rel))]
    for rel in bad:
        print("  ✗ %s" % rel)
    if bad:
        sys.exit("有 %d 个文件不一致 —— 未推送，请修正后重跑" % len(bad))
    print("  ✔ 全部 %d 个文件一致" % len(files))
    print("\n提交历史（最近 20 条）：")
    print(git("log", "--oneline", "-20"))


if __name__ == "__main__":
    main()
