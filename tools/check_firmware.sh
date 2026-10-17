#!/bin/sh
# 从**编出来的固件镜像**里读已装包清单，校验"该带的带上、不该带的没有"。
#
# 为什么不信 .manifest：x-wrt 26.10 是 CONFIG_TARGET_PER_DEVICE_ROOTFS=y，
# bin/targets 下那个 *.manifest 是 **target 级（模板 rootfs）** 的清单，
# 不含各机型的 DEVICE_PACKAGES。真正的安装清单在镜像里的
#   /lib/apk/db/installed      （x-wrt 用 apk，不是 opkg！）
#
# 用法： sh tools/check_firmware.sh [产物目录] [x-wrt 树]
set -u
OUT=${1:-$HOME/hinlink-out-xwrt}
TREE=${2:-$HOME/xwrt-hinlink}
UNSQ=$TREE/staging_dir/host/bin/unsquashfs4
WORK=$(mktemp -d "${TMPDIR:-/tmp}/hinchk.XXXXXX") || exit 1
trap 'rm -rf "$WORK"' EXIT

FAN="h69k h69k-mini h88k-v2 h88k-v3 h89k"
MODEM="h29k-v1.3-1.14 h29k-v5-1.14 h29k-v5-1.49 h69k h69k-mini h88k-v2 h88k-v3 h89k"

printf "%-16s %-6s %-5s %-5s %-5s %-6s %s\n" 机型 包数 风扇 5G OLED 序号 说明
bad=0; n=0
for d in "$OUT"/*/; do
	[ -d "$d" ] || continue
	s=$(basename "$d")
	img=$(ls "$d"*-squashfs-sysupgrade.img.gz 2>/dev/null | head -1)
	[ -n "$img" ] || { printf "%-16s 缺镜像\n" "$s"; bad=$((bad+1)); continue; }
	n=$((n+1))
	gzip -dc "$img" > "$WORK/i.bin" 2>/dev/null
	off=$(python3 - "$WORK/i.bin" <<'PY'
import sys
d=open(sys.argv[1],'rb').read(400*1024*1024)
print(d.find(b'hsqs'))
PY
)
	rm -rf "$WORK/root"
	"$UNSQ" -o "$off" -d "$WORK/root" -f "$WORK/i.bin" >/dev/null 2>&1
	DB="$WORK/root/lib/apk/db/installed"
	if [ ! -f "$DB" ]; then printf "%-16s 解包失败(off=%s)\n" "$s" "$off"; bad=$((bad+1)); continue; fi
	cnt=$(grep -c "^P:" "$DB")
	wf=0; wm=0
	for x in $FAN;   do [ "$x" = "$s" ] && wf=1; done
	for x in $MODEM; do [ "$x" = "$s" ] && wm=1; done
	gf=0; grep -q "^P:luci-app-fancontrol$" "$DB" && gf=1
	gm=0; grep -q "^P:luci-app-hinlink-modem-hardreset$" "$DB" && gm=1
	go=0; grep -q "^P:luci-app-oled$" "$DB" && go=1
	msg=""; [ "$gf" = "$wf" ] || { msg="$msg 风扇不符"; bad=$((bad+1)); }
	[ "$gm" = "$wm" ] || { msg="$msg 5G面板不符"; bad=$((bad+1)); }
	[ "$go" = 1 ] || { msg="$msg 缺OLED"; bad=$((bad+1)); }
	y() { [ "$1" = 1 ] && echo Y || echo -; }
	printf "%-16s %-6s %-5s %-5s %-5s %-6s %s\n" "$s" "$cnt" "$(y $gf)" "$(y $gm)" "$(y $go)" "$n" "${msg:-OK}"
done

echo
echo "检查 $n 个机型，问题数: $bad"
[ "$bad" = 0 ]
