#!/usr/bin/env python3
"""Repack a Qualcomm Android boot image v0/v1 with a new kernel and ramdisk.

  repack_bootv0.py TEMPLATE KERNEL RAMDISK OUT [--cmdline STR] [--second FILE]

The OnePlus 5 bootloader expects the Android boot header v0 (and possibly a
QCDT table appended after the second stage), not the v2 header used by sweet.
This tool keeps the stock header fields, load addresses and the entire tail
(padding + QCDT + stock DTB entries), replaces the kernel and ramdisk, and
recomputes the v0 SHA-1 id.  The bootloader still selects its own DTB from the
unchanged QCDT and passes it to the shim in x0.

Only v0/v1 images are accepted.  Use the AOSP mkbootimg for v2.
"""
import argparse
import hashlib
import struct
import sys

BOOT_MAGIC = b'ANDROID!'
BOOT_ARGS_SIZE = 512
BOOT_EXTRA_ARGS_SIZE = 1024
ID_OFF = 0x240
EXTRA_CMDLINE_OFF = 0x248


def align(n, page):
    return (n + page - 1) & ~(page - 1)


def parse_header(data):
    if len(data) < 0x2c or data[:8] != BOOT_MAGIC:
        raise SystemExit('not an Android boot image (magic mismatch)')
    (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
     second_size, second_addr, tags_addr, page_size,
     header_version, os_version) = struct.unpack_from('<10I', data, 8)
    if header_version not in (0, 1):
        raise SystemExit(f'boot header v{header_version} is not v0/v1; use mkbootimg')
    if page_size < 2048 or page_size > 65536 or page_size & (page_size - 1):
        raise SystemExit(f'bad page size {page_size}')
    return dict(kernel_size=kernel_size, kernel_addr=kernel_addr,
                ramdisk_size=ramdisk_size, ramdisk_addr=ramdisk_addr,
                second_size=second_size, second_addr=second_addr,
                tags_addr=tags_addr, page_size=page_size,
                header_version=header_version, os_version=os_version)


def describe_qcdt(tail, tail_off):
    pos = tail.find(b'QCDT')
    if pos < 0:
        return 'no QCDT magic in tail'
    if pos + 32 > len(tail):
        return 'truncated QCDT'
    magic, total, hsize, esize, count, eoff, psize, ver = struct.unpack_from('<8I', tail, pos)
    if hsize < 32 or esize < 24 or count > 64 or eoff < hsize:
        return f'QCDT magic at +{pos} (suspicious header)'
    return (f'QCDT at file +{tail_off + pos}: total={total} header={hsize} '
            f'entry={esize} count={count} page={psize} version={ver}')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('template')
    ap.add_argument('kernel')
    ap.add_argument('ramdisk')
    ap.add_argument('out')
    ap.add_argument('--cmdline')
    ap.add_argument('--second', help='replacement second-stage blob (optional)')
    args = ap.parse_args()

    template = open(args.template, 'rb').read()
    h = parse_header(template)
    page = h['page_size']
    kernel = open(args.kernel, 'rb').read()
    ramdisk = open(args.ramdisk, 'rb').read()
    second = open(args.second, 'rb').read() if args.second else template[
        page + align(h['kernel_size'], page) + align(h['ramdisk_size'], page):
        page + align(h['kernel_size'], page) + align(h['ramdisk_size'], page) + h['second_size']]
    if not kernel or not ramdisk:
        raise SystemExit('kernel and ramdisk must be non-empty')

    # The first page is the padded v0/v1 header.  After the three padded
    # sections the rest is Qualcomm padding + QCDT/DTB and is kept verbatim.
    tail_off = page + align(h['kernel_size'], page) + align(h['ramdisk_size'], page) + \
        align(h['second_size'], page)
    tail = template[tail_off:]
    print(describe_qcdt(tail, tail_off), file=sys.stderr)

    header = bytearray(template[:page])
    struct.pack_into('<I', header, 0x08, len(kernel))
    struct.pack_into('<I', header, 0x10, len(ramdisk))
    struct.pack_into('<I', header, 0x18, len(second))
    if args.cmdline is not None:
        cmd = args.cmdline.encode()
        if len(cmd) >= BOOT_ARGS_SIZE:
            raise SystemExit(f'cmdline too long ({len(cmd)} >= {BOOT_ARGS_SIZE})')
        header[0x40:0x40 + BOOT_ARGS_SIZE] = cmd + b'\0' * (BOOT_ARGS_SIZE - len(cmd))
        header[EXTRA_CMDLINE_OFF:EXTRA_CMDLINE_OFF + BOOT_EXTRA_ARGS_SIZE] = \
            b'\0' * BOOT_EXTRA_ARGS_SIZE
    # v0/v1 id: SHA-1 over kernel, ramdisk and second stage.
    header[ID_OFF:ID_OFF + 32] = hashlib.sha1(kernel + ramdisk + second).digest() + b'\0' * 12

    out = bytearray()
    out += header
    out += kernel + b'\0' * (align(len(kernel), page) - len(kernel))
    out += ramdisk + b'\0' * (align(len(ramdisk), page) - len(ramdisk))
    out += second + b'\0' * (align(len(second), page) - len(second))
    out += tail
    open(args.out, 'wb').write(out)
    print(f'{args.out}: {len(out)} bytes (header v{h["header_version"]}, '
          f'page={page}, kernel={len(kernel)}, ramdisk={len(ramdisk)}, '
          f'second={len(second)}, tail={len(tail)})', file=sys.stderr)


if __name__ == '__main__':
    main()
