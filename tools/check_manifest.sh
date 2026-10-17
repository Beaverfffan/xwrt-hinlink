#!/bin/sh
# 校验编出来的 .manifest：该带的包带上了、不该带的没有。
#
# 为什么不能只看 .config —— 官方模板是 CONFIG_TARGET_PER_DEVICE_ROOTFS=y，
# 每机型独立 rootfs，"这台机器装什么"由 image.mk 里该 device 的
# DEVICE_PACKAGES 在打包时决定，.config 里的 CONFIG_PACKAGE_*=m 是正常的。
# 唯一可信的证据就是产物里的 .manifest。
#
#   sh tools/check_manifest.sh [产物目录，默认 ~/hinlink-out-xwrt]
set -u

OUT=${1:-$HOME/hinlink-out-xwrt}

FAN="h69k h69k-mini h88k-v2 h88k-v3 h89k"
MODEM="h29k-v1.3-1.14 h29k-v5-1.14 h29k-v5-1.49 h69k h69k-mini h88k-v2 h88k-v3 h89k"

has() { grep -qE "^$2 " "$1" 2>/dev/null; }

bad=0
printf "%-16s %-8s %-6s %-6s %-6s %s\n" 机型 manifest 风扇 5G OLED 说明
for d in "$OUT"/*/; do
	[ -d "$d" ] || continue
	s=$(basename "$d")
	m=$(ls "$d"*.manifest 2>/dev/null | head -1)
	[ -n "$m" ] || { printf "%-16s %s\n" "$s" "缺 manifest"; bad=$((bad+1)); continue; }

	want_fan=0; want_modem=0
	for x in $FAN;   do [ "$x" = "$s" ] && want_fan=1;   done
	for x in $MODEM; do [ "$x" = "$s" ] && want_modem=1; done

	got_fan=0;   has "$m" luci-app-fancontrol && got_fan=1
	got_modem=0; has "$m" luci-app-hinlink-modem-hardreset && got_modem=1
	got_oled=0;  has "$m" luci-app-oled && got_oled=1

	msg=""
	[ "$got_fan"   = "$want_fan"   ] || { msg="$msg 风扇不符";   bad=$((bad+1)); }
	[ "$got_modem" = "$want_modem" ] || { msg="$msg 5G面板不符"; bad=$((bad+1)); }
	[ "$got_oled" = 1 ] || { msg="$msg 缺OLED"; bad=$((bad+1)); }

	ok() { [ "$1" = 1 ] && echo Y || echo -; }
	printf "%-16s %-8s %-6s %-6s %-6s %s\n" "$s" "$(grep -c "" "$m")" \
		"$(ok $got_fan)" "$(ok $got_modem)" "$(ok $got_oled)" "${msg:-OK}"
done

echo
echo "问题数: $bad"
[ "$bad" = 0 ]
