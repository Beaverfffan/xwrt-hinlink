#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 16 份**单机型** .config（x-wrt 专用，基于官方模板）。

★ 为什么不再"自己攒一份底稿"
------------------------------
x-wrt 的 target 默认配置（natflow / natcap / base-config-setting / luci 全套 /
默认分区 ……）全在官方模板里：

    feeds/x/rom/lede/config.rockchip-armv8          （约 9990 行，官方 rc 配置）
    feeds/x/rom/lede/fix-config.sh                  （选完机型后必须跑）

官方流程（用户 2026-10-17 明确）：

    cp feeds/x/rom/lede/config.rockchip-armv8 .config
    # 选机型（改 CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_<name>）
    sh feeds/x/rom/lede/fix-config.sh
    make defconfig && make -j$(nproc)

`fix-config.sh` 做的事：把 `.config` 里所有 `CONFIG_DEFAULT_<pkg>=y` 对应的
`CONFIG_PACKAGE_<pkg>=m` 改成 `=y`（"设备默认包"由模块改成内建），
只有 dnsmasq 例外 —— 改成 `# … is not set`；另外补一把 apk。

本脚本在此基础上按机型收敛，并额外写死：
  · 分区（默认 128 / 1024，仅影响镜像 padding，不参与编译）
  · CONFIG_VERSION_NUMBER（固件里能看出是哪次 release）
  · 只留一个设备符号（MULTI_PROFILE=y 下必须如此）

⚠️ 不要在这里再手工注入风扇 / 5G 面板 ——
   它们已经写在 `target/linux/rockchip/image/armv8.mk.hinlink` 的
   DEVICE_PACKAGES 里（两条独立判据：有风扇就风扇、有复位脚就复位脚）。
   device 定义是**唯一源**，这里只做**校验**。

用法（在 x-wrt 树根）：
    python3 tools/gen_configs.py [树路径] [--parts=128/1024] [--no-parts]
"""
import os
import re
import shutil
import subprocess
import sys

TPL_REL = "feeds/x/rom/lede/config.rockchip-armv8"
FIX_REL = "feeds/x/rom/lede/fix-config.sh"

PREFIX = "CONFIG_TARGET_DEVICE_rockchip_armv8_DEVICE_"

# (configs/ 文件名, OpenWrt DEVICE 名)
DEVICES = [
    ("h28k",           "hinlink_h28k_rk3528"),
    ("h29k-v1.3-1.14", "hinlink_h29k-v1.3-1.14_rk3528"),
    ("h29k-v5-1.14",   "hinlink_h29k-v5-1.14_rk3528"),
    ("h29k-v5-1.49",   "hinlink_h29k-v5-1.49_rk3528"),
    ("ht2",            "hinlink_opc-ht2_rk3528"),
    ("h66k",           "hinlink_opc-h66k"),
    ("h68k-a-b",       "hinlink_opc-h68k-a-b"),
    ("h68k-a-b-usb",   "hinlink_opc-h68k-a-b-usb"),
    ("h68k-c-d-f",     "hinlink_opc-h68k-c-d-f"),
    ("h68k-c-d-f-usb", "hinlink_opc-h68k-c-d-f-usb"),
    ("h68k-new",       "hinlink_opc-h68k-new"),
    ("h69k",           "hinlink_opc-h69k"),
    ("h69k-mini",      "hinlink_opc-h69k-mini"),
    ("h88k-v2",        "hinlink_h88k_v2"),
    ("h88k-v3",        "hinlink_h88k_v3"),
    ("h89k",           "hinlink_opc-h89k_rk3588"),
]

# ★ 两条**独立**判据，别取交集（取交集会把"有复位脚但没风扇"的 H29K 全系漏掉）
HAS_FAN = {"h69k", "h69k-mini", "h88k-v2", "h88k-v3", "h89k"}
HAS_MODEM = {"h29k-v1.3-1.14", "h29k-v5-1.14", "h29k-v5-1.49",
             "h69k", "h69k-mini", "h88k-v2", "h88k-v3", "h89k"}

# 必选（16 机型全带）
MUST_KEEP = [
    "luci-app-oled",
    "kmod-mt7921e", "kmod-mt7922-firmware", "kmod-mt7925e",
    "kmod-mt7915e", "kmod-mt7916-firmware",
    "kmod-ath11k", "kmod-ath11k-pci", "ath11k-firmware-wcn6855",
    "kmod-aic8800-pcie", "kmod-aic8800-sdio", "kmod-aic8800-usb",
    "kmod-r8169",
]

VER_NUMBER = "16dev-2026.10.17"


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, shell=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)


def build_one(tpl, dev, parts, version):
    out = []
    for ln in tpl.splitlines():
        m = re.match(r'^(?:# )?' + re.escape(PREFIX) + r'([^\s=]+)', ln)
        if m:
            name = m.group(1)
            out.append("%s%s=%s" % (PREFIX, name,
                                    "y" if name == dev else "n"))
            continue
        if ln.startswith("CONFIG_TARGET_PROFILE="):
            continue                        # MULTI_PROFILE 下由设备符号决定
        if parts and ln.startswith("CONFIG_TARGET_KERNEL_PARTSIZE="):
            out.append("CONFIG_TARGET_KERNEL_PARTSIZE=%d" % parts[0])
            continue
        if parts and ln.startswith("CONFIG_TARGET_ROOTFS_PARTSIZE="):
            out.append("CONFIG_TARGET_ROOTFS_PARTSIZE=%d" % parts[1])
            continue
        if ln.startswith("CONFIG_VERSION_NUMBER="):
            out.append('CONFIG_VERSION_NUMBER="%s"' % version)
            continue
        out.append(ln)

    out.append("# ---- HinLink：本机型 ----")
    out.append("%s%s=y" % (PREFIX, dev))
    return "\n".join(out) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tree = os.path.expanduser(args[0]) if args else os.path.expanduser("~/xwrt-hinlink")

    parts = (128, 1024)
    if "--no-parts" in sys.argv:
        parts = None
    for a in sys.argv[1:]:
        if a.startswith("--parts="):
            k, r = a.split("=", 1)[1].split("/")
            parts = (int(k), int(r))

    tpl_p = os.path.join(tree, TPL_REL)
    fix_p = os.path.join(tree, FIX_REL)
    if not os.path.isfile(tpl_p):
        sys.exit("找不到官方模板 %s（先 ./scripts/feeds install -a）" % tpl_p)
    if not os.path.isfile(fix_p):
        sys.exit("找不到 %s" % fix_p)

    tpl = open(tpl_p, encoding="utf-8").read()
    outdir = os.path.join(tree, "configs")
    os.makedirs(outdir, exist_ok=True)
    cfgp = os.path.join(tree, ".config")

    print("底稿: %s（%d 行）" % (TPL_REL, len(tpl.splitlines())))
    print("分区: %s    版本号: %s"
          % ("%d/%d" % parts if parts else "官方默认", VER_NUMBER))
    print("风扇（有风扇）      -> %s" % " ".join(sorted(HAS_FAN)))
    print("5G 复位面板（有脚） -> %s\n" % " ".join(sorted(HAS_MODEM)))

    ok = fail = 0
    for short, dev in DEVICES:
        p = os.path.join(outdir, short + ".config")
        open(p, "w", encoding="utf-8", newline="\n").write(
            build_one(tpl, dev, parts, VER_NUMBER))
        shutil.copy(p, cfgp)

        # ★ 官方流程的关键**顺序**（2026-10-17 踩过）：
        #   fix-config.sh 是按 `.config` 里已存在的 `CONFIG_DEFAULT_<pkg>=y`
        #   行来把对应的 `CONFIG_PACKAGE_<pkg>=m` 改成 `=y`。
        #   而 DEFAULT_ 符号是 **defconfig 之后**才由 kconfig 物化出来的
        #   ⇒ 必须先 defconfig、再 fix-config、再 defconfig 收敛。
        #   先跑 fix-config 的话它只看到模板里那 28 条 target 级 DEFAULT_，
        #   设备包一条都改不到（表现为 kmod-mt7921e 等仍是 =m）。
        bad = False
        for cmd, tag in (("make defconfig", "defconfig#1"),
                         ("sh %s" % FIX_REL, "fix-config.sh"),
                         ("make defconfig", "defconfig#2")):
            r = sh(cmd, tree)
            if r.returncode != 0:
                print("!! %-16s %s 失败" % (short, tag))
                print((r.stdout or "")[-1200:])
                fail += 1
                bad = True
                break
        if bad:
            continue

        shutil.copy(cfgp, p)
        after = open(p, encoding="utf-8").read()

        # ★ 官方模板里 CONFIG_TARGET_PER_DEVICE_ROOTFS=y（每机型独立 rootfs）。
        #   这种模式下"某机型装哪些包"**不由 CONFIG_PACKAGE_*=y 决定**，
        #   而是由 image.mk 里该 device 的 DEVICE_PACKAGES 在打包时决定
        #   （所以 kmod-mt7921e / fancontrol 在 .config 里是 =m 属正常）。
        #   ⇒ 这里只校验"机型 / 分区 / 版本"，
        #     包的实际归属用**构建出来的 .manifest** 校验（tools/check_manifest.sh）。
        pdr = "CONFIG_TARGET_PER_DEVICE_ROOTFS=y" in after
        sel = re.findall(re.escape(PREFIX) + r'([^\s=]+)=y', after)
        got = sel[0] if sel else "?"
        miss = []
        if len(sel) != 1 or got != dev:
            miss.append("机型不符(%d 个设备:%s)" % (len(sel), ",".join(sel) or "无"))
        if not pdr:
            miss.append("PER_DEVICE_ROOTFS 不是 y")
        if parts:
            if ("CONFIG_TARGET_KERNEL_PARTSIZE=%d" % parts[0]) not in after:
                miss.append("内核分区不是 %d" % parts[0])
            if ("CONFIG_TARGET_ROOTFS_PARTSIZE=%d" % parts[1]) not in after:
                miss.append("rootfs 分区不是 %d" % parts[1])

        tag = "OK"
        if miss:
            tag = "有问题(%d)" % len(miss)
            fail += 1
        else:
            ok += 1

        apps = ("风扇" if short in HAS_FAN else "..") + "/" + \
               ("5G" if short in HAS_MODEM else "..")
        print("%-16s %-12s 插件=%-8s lines=%-5d device=%s"
              % (short, tag, apps, len(after.splitlines()), got))
        if miss:
            print("                 缺失: %s" % " ".join(miss))

    print("\n完成：%d 成功 / %d 有问题" % (ok, fail))


if __name__ == "__main__":
    main()
