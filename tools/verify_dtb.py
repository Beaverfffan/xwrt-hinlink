#!/usr/bin/env python3
"""反编译 DTB，核查本轮修复是否真的生效。"""
import io, re, subprocess, sys, os

DTC = sys.argv[1]
DIR = sys.argv[2]
fails = [0]

def to_dts(dtb):
    r = subprocess.run([DTC, "-I", "dtb", "-O", "dts", dtb],
                       capture_output=True, text=True)
    return r.stdout

def check(desc, cond, detail=""):
    print("    %s %-46s %s" % ("✅" if cond else "❌", desc, detail))
    if not cond:
        fails[0] += 1

CHECKS = {
  'rk3568-hinlink-h69k-3eth': [
    ("gmac1 (fe010000) = okay",
     lambda t: re.search(r'ethernet@fe010000 \{[^}]*status = "okay"', t, re.S) is not None),
    ("gmac0 (fe2a0000) = disabled",
     lambda t: re.search(r'ethernet@fe2a0000 \{[^}]*status = "disabled"', t, re.S) is not None),
    ("aliases ethernet0 -> fe010000 (gmac1)",
     lambda t: 'ethernet0 = "/ethernet@fe010000"' in t),
  ],
}

FILES = ['rk3528-hinlink-h28k', 'rk3528-hinlink-h29k-v1.3-1.14', 'rk3528-hinlink-ht2',
         'rk3568-hinlink-h66k', 'rk3568-hinlink-h68k-c', 'rk3568-hinlink-h68k-d',
         'rk3568-hinlink-h69k-3eth', 'rk3568-hinlink-h69k-mini',
         'rk3588-hinlink-h88k-v3', 'rk3588-hinlink-h89k']

print("=" * 80)
print("DTB 内容核查（反编译自 /tmp/dtscheck/*.dtb）")
for b in FILES:
    dtb = os.path.join(DIR, b + ".dtb")
    if not os.path.exists(dtb):
        print("  %-34s ❌ 无 dtb" % b); fails[0] += 1; continue
    t = to_dts(dtb)
    print("  %s" % b)
    check("LED 状态别名 led-boot/led-running",
          'led-boot' in t and 'led-running' in t)
    m = re.search(r'compatible = ([^;]+);', t)
    print("       compatible = %s" % (re.sub(r'\s+', ' ', m.group(1)) if m else '?'))
    for a in re.findall(r'(ethernet\d) = "([^"]+)"', t):
        print("       %-10s -> %s" % a)
    for desc, fn in CHECKS.get(b, []):
        check(desc, fn(t))

print("=" * 80)
print("未通过项: %d" % fails[0])
sys.exit(1 if fails[0] else 0)
