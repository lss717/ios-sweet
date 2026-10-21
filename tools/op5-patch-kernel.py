#!/usr/bin/env python3
"""Patch an OP5 xnu kernel image so the closed-source libfirehose_kernel does
not execute LSE atomics (Kryo 280 has no LSE).

Apple ships libfirehose_kernel as a prebuilt object compiled for Apple cores,
so it contains ldadd/casa/stadd.  Logging is not needed for bring-up; replace
the entry of the firehose init and stream functions with `ret` (both are void).

  op5-patch-kernel.py IN OUT
"""
import struct
import sys

RET = struct.pack('<I', 0xD65F03C0)

PATCH = ('_oslog_init_firehose', '_oslog_stream')


def symbols(f):
    ncmds = struct.unpack_from('<I', f, 16)[0]
    off = 32
    syms = {}
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', f, off)
        if cmd == 0x2:  # LC_SYMTAB
            symoff, nsyms, stroff, _ = struct.unpack_from('<4I', f, off + 8)
            for i in range(nsyms):
                n_strx, _, _, _, n_value = struct.unpack_from('<IBBHQ', f, symoff + i * 16)
                end = f.index(b'\0', stroff + n_strx)
                syms[f[stroff + n_strx:end].decode('utf-8', 'replace')] = n_value
        off += size
    return syms


def segments(f):
    ncmds = struct.unpack_from('<I', f, 16)[0]
    off = 32
    segs = []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', f, off)
        if cmd == 0x19:  # LC_SEGMENT_64
            vm, vs, fo, fs = struct.unpack_from('<4Q', f, off + 24)
            segs.append((vm, fo, fs))
        off += size
    return segs


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    data = bytearray(open(sys.argv[1], 'rb').read())
    syms = symbols(bytes(data))
    segs = segments(bytes(data))
    for name in PATCH:
        va = syms.get(name)
        if va is None:
            raise SystemExit(f'{name} not found')
        for vm, fo, fs in segs:
            if vm <= va < vm + fs:
                data[fo + (va - vm):fo + (va - vm) + 4] = RET
                print(f'{name} @ {va:#x}: patched to ret')
                break
        else:
            raise SystemExit(f'{name} @ {va:#x}: no segment')
    open(sys.argv[2], 'wb').write(data)


if __name__ == '__main__':
    main()
