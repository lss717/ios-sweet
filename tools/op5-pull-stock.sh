#!/bin/sh
# Pull the OnePlus 5 stock partitions needed for the iOS bring-up.
#
#   tools/op5-pull-stock.sh [OUTDIR]      (default: backup/op5)
#
# Run with the phone in TWRP via `fastboot boot twrp.img` (adb root).  This
# only reads partitions; it never writes to the phone.  userdata is not pulled
# (128 GB); its size and block device are printed instead.
#
# The output contains device-specific calibration/serial data.  backup/ is in
# .gitignore: keep these files out of git.
set -eu

out=${1:-backup/op5}
ADB=${ADB:-adb}
command -v "$ADB" >/dev/null 2>&1 || { echo "error: adb not found" >&2; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "error: sha256sum not found" >&2; exit 1; }

"$ADB" get-state >/dev/null 2>&1 || { echo "error: no adb device (boot TWRP first)" >&2; exit 1; }
id=$("$ADB" shell id 2>/dev/null | tr -d '\r')
case "$id" in
	*uid=0*) ;;
	*) echo "warning: adb shell is not root ($id); partition reads may fail" >&2 ;;
esac

mkdir -p "$out"
for p in boot dtbo vbmeta recovery persist modemst1 modemst2 fsg fsc; do
	dev=$("$ADB" shell "for d in /dev/block/by-name/$p /dev/block/bootdevice/by-name/$p; do [ -e \$d ] && readlink -f \$d && break; done" 2>/dev/null | tr -d '\r')
	if [ -z "$dev" ]; then
		echo "skip $p: no block device" >&2
		continue
	fi
	echo "pulling $p from $dev"
	"$ADB" exec-out "dd if=$dev bs=1048576 2>/dev/null" > "$out/$p.img"
	ls -l "$out/$p.img"
done

for p in userdata; do
	dev=$("$ADB" shell "for d in /dev/block/by-name/$p /dev/block/bootdevice/by-name/$p; do [ -e \$d ] && readlink -f \$d && break; done" 2>/dev/null | tr -d '\r')
	if [ -n "$dev" ]; then
		printf '%s: %s, %s bytes\n' "$p" "$dev" "$("$ADB" shell blockdev --getsize64 "$dev" | tr -d '\r')"
	fi
done

(cd "$out" && sha256sum ./*.img > SHA256SUMS)
echo "wrote $out/SHA256SUMS"

if command -v unpack_bootimg >/dev/null 2>&1 && [ -f "$out/boot.img" ]; then
	rm -rf "$out/boot-unpacked"
	unpack_bootimg --boot_img "$out/boot.img" --out "$out/boot-unpacked" || true
	python3 - "$out/boot.img" <<'PY'
import sys
d = open(sys.argv[1], 'rb').read()
pos = d.find(b'QCDT')
if pos < 0:
    print('boot.img: no QCDT magic')
else:
    import struct
    magic, total, hsize, esize, count, eoff, page, ver = struct.unpack_from('<8I', d, pos)
    print(f'boot.img: QCDT at +{pos}, total={total}, header={hsize}, '
          f'entry={esize}, count={count}, page={page}, version={ver}')
PY
fi

echo "done. Keep $out off git (device calibration data)."
