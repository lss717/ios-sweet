#!/bin/bash
# Build the shim and wrap it in a boot image.
#
#   BOARD=sweet ./build.sh [payload.bin]     # default, boot.img v2
#   BOARD=op5   ./build.sh [payload.bin]     # OnePlus 5, v0/QCDT repack
#   PACKAGE=0   ./build.sh                   # compile only (no boot image)
#
# For BOARD=op5 the boot image packaging needs a stock boot.img template:
#   OP5_BOOT_TEMPLATE=/path/to/boot.img BOARD=op5 ./build.sh payload.bin
# tools/repack_bootv0.py keeps the stock header and QCDT, replacing only the
# kernel and ramdisk.  See docs/ONEPLUS5.md.
set -euo pipefail
cd "$(dirname "$0")"
BOARD=${BOARD:-sweet}
case "$BOARD" in
	sweet) BOARD_DEFS="" ;;
	op5)   BOARD_DEFS="-DBOARD_OP5" ;;
	*)     echo "error: unknown BOARD=$BOARD (sweet|op5)" >&2; exit 2 ;;
esac
PACKAGE=${PACKAGE:-1}
CC=aarch64-linux-gnu-gcc
OBJCOPY=aarch64-linux-gnu-objcopy
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra $BOARD_DEFS"
mkdir -p out
for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done
# The image runs wherever ABL puts it with no relocation pass: only the
# header's image_size (start.o, linked at 0) may be an absolute address.
abs=$(aarch64-linux-gnu-readelf -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
# ABL copies the file; pad to image_size so .bss/stacks exist as zeroed bytes.
size=$(aarch64-linux-gnu-nm out/shim.elf | awk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out/Image
# Ramdisk: an xnu payload (tools/mkpayload.py) if given as $1, else an empty
# newc cpio (ABL dislikes a zero-size ramdisk on some builds) -> diagnostics.
if [ -n "${1:-}" ]; then
	cp "$1" out/ramdisk.bin
else
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi
if [ "$PACKAGE" = 1 ]; then
	if [ "$BOARD" = op5 ]; then
		: "${OP5_BOOT_TEMPLATE:?set OP5_BOOT_TEMPLATE to the stock OnePlus 5 boot.img}"
		# OP5 ABL expects Image.gz + appended DTBs (there is no QCDT in the
		# stock boot image).  repack_bootv0.py copies the stock DTB tail
		# after the gzip stream and trims the all-zero partition padding.
		gzip -n -9 -c out/Image > out/Image.gz
		python3 ../tools/repack_bootv0.py --trim "$OP5_BOOT_TEMPLATE" \
			out/Image.gz out/ramdisk.bin out/shim-boot.img
	else
		command -v mkbootimg >/dev/null 2>&1 || {
			echo "error: mkbootimg not found (install Android platform tools)" >&2; exit 1; }
		mkbootimg --header_version 2 --kernel out/Image --ramdisk out/ramdisk.bin \
			--dtb ../dtb/boot_unpacked/dtb --base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
			--tags_offset 0x100 --dtb_offset 0x1f00000 --pagesize 4096 \
			--os_version 17.0.0 --os_patch_level 2035-06 \
			--cmdline "console=null" -o out/shim-boot.img
	fi
fi
# Host render of the console layout (same board constants).
gcc -O1 -Wall $BOARD_DEFS -o out/host_test console.c host_test.c && ./out/host_test
if [ "$PACKAGE" = 1 ]; then
	ls -l out/Image out/shim-boot.img
else
	ls -l out/Image
fi
