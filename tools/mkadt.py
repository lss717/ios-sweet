#!/usr/bin/env python3
"""Build the minimal Apple Device Tree that the SWEET xnu needs to boot.

Only what the early boot path actually reads (see NOTES.md); every MMIO
address comes from the board profile. Usage:

  mkadt.py OUT.adt [--board sweet|op5] [--dump] [--qemu] [--highmem]

`sweet` (default) is the Redmi Note 10 Pro / SM7150 target.  `op5` is the
OnePlus 5 / MSM8998 target and uses the iPhone 8 Plus identity (D21AP).
"""
import argparse, hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402

SWEET_ECID = 0x5357454554000001  # 'SWEET' + 1, synthetic
BOOT_MANIFEST_HASH = hashlib.sha384(b'sweet boot manifest').digest()

# QEMU virt (-M virt,gic-version=3 -cpu cortex-a76): GICD/GICR and CNTFRQ.
QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE = 0x08000000, 0x080a0000, 62500000
QEMU_VTIMER_INTID = 27

HERE = os.path.dirname(os.path.abspath(__file__))

# CPU entries: (MPIDR, cluster-id, cluster-core-id, l2-cache-id, Hz).
# MPIDR is Aff1:Aff0 as the boot ROM/PSCI sees it, not a logical index.
SWEET_CPUS = [
    (0x000, 0, 0, 0, 1804800000),
    (0x100, 0, 1, 1, 1804800000),
    (0x200, 0, 2, 2, 1804800000),
    (0x300, 0, 3, 3, 1804800000),
    (0x400, 0, 4, 4, 1804800000),
    (0x500, 0, 5, 5, 1804800000),
    (0x600, 0, 6, 6, 2304000000),
    (0x700, 0, 7, 7, 2304000000),
]
# OnePlus 5: 4x Cortex-A53 (cluster 0), 4x Cortex-A73 (cluster 1).
# Both clusters are presented as one homogeneous SMP cluster for the first
# bring-up; cluster-id stays 0 so the existing SweetCPU code can start them.
OP5_CPUS = [
    (0x000, 0, 0, 0, 1900800000),
    (0x001, 0, 1, 0, 1900800000),
    (0x002, 0, 2, 0, 1900800000),
    (0x003, 0, 3, 0, 1900800000),
    (0x100, 0, 4, 1, 2457600000),
    (0x101, 0, 5, 1, 2457600000),
    (0x102, 0, 6, 1, 2457600000),
    (0x103, 0, 7, 1, 2457600000),
]

BOARDS = {
    'sweet': {
        'name': 'sweet',
        'desc': 'Redmi Note 10 Pro (SM7150)',
        'phys_base': 0xb0000000,
        'mem_size': 0x4d000000,
        'high_phys_base': 0x100000000,
        'high_mem_size': 0xfcc00000,
        'soc_base': 0x01000000,
        'gicd': 0x17a00000, 'gicd_size': 0x10000,
        'gicr': 0x17a60000, 'gicr_size': 0x100000,
        'fb': 0x9c000000, 'fb_size': 0x1700000,
        'fb_w': 1080, 'fb_h': 2400, 'fb_stride': 1080 * 4,
        'canvas_w': 1125, 'canvas_h': 2436,
        'ufs': 0x01d84000, 'ufs_size': 0x3000,
        'timebase': 19200000, 'vtimer': 19,
        'cpus': SWEET_CPUS,
        'cpu_compatible': 'qcom,kryo470',
        'product_adt': os.path.join(HERE, '../research/ipsw-x/d22ap.adt'),
        'compatible': ('D22AP', 'iPhone10,3', 'xiaomi,sweet', 'qcom,sm7150', 'AppleARM'),
        'model': 'iPhone10,3', 'target': 'D22', 'target_sub': 'D22AP',
        'display_scale': 3,
        'home_button_type': 2,
    },
    'op5': {
        'name': 'op5',
        'desc': 'OnePlus 5 (MSM8998)',
        'phys_base': 0xb0000000,
        'mem_size': 0x4d000000,
        # 8 GB OP5: low bank 2 GB, high bank 6 GB. Start with the same
        # conservative window as sweet, then grow from the live FDT.
        'high_phys_base': 0x100000000,
        'high_mem_size': 0xfcc00000,
        'soc_base': 0x01000000,
        'gicd': 0x17a00000, 'gicd_size': 0x10000,
        'gicr': 0x17b00000, 'gicr_size': 0x100000,
        # ABL cont_splash_mem in the MSM8998 device tree.
        'fb': 0x9d600000, 'fb_size': 0x02400000,
        'fb_w': 1080, 'fb_h': 1920, 'fb_stride': 1080 * 4,
        # iPhone 8 Plus renders 1242x2208 @3x and downsamples to 1080x1920.
        'canvas_w': 1242, 'canvas_h': 2208,
        'ufs': 0x01da4000, 'ufs_size': 0x3000,
        'timebase': 19200000, 'vtimer': 19,
        'cpus': OP5_CPUS,
        'cpu_compatible': 'qcom,kryo280',
        'product_adt': os.path.join(HERE, '../research/ipsw-x/d21ap.adt'),
        'compatible': ('D21AP', 'iPhone10,2', 'oneplus,cheeseburger', 'qcom,msm8998', 'AppleARM'),
        'model': 'iPhone10,2', 'target': 'D21', 'target_sub': 'D21AP',
        'display_scale': 3,
        # Real D21AP /buttons: 1 = Home button (iPhone 8 Plus).
        'home_button_type': 1,
    },
}

u32 = lambda *v: struct.pack('<%dI' % len(v), *v)
u64 = lambda *v: struct.pack('<%dQ' % len(v), *v)
cstr = lambda s: s.encode() + b'\0'


def node(name, props=(), children=()):
    n = adt.Node()
    n.props = [('name', 0, cstr(name))] + [(k, 0, v) for k, v in props]
    n.children = list(children)
    return n


def product_props(path):
    """/product properties of the real device tree, without the syscfg
    placeholders iBoot would fill in (flag bit set) and node bookkeeping."""
    if not os.path.exists(path):
        print(f'warning: {path} missing, no /product node', file=sys.stderr)
        return None
    root, _ = adt.parse(open(path, 'rb').read())
    for c in root.children:
        if dict((k, v) for k, f, v in c.props).get('name') == b'product\0':
            return [(k, v) for k, f, v in c.props if not f and k not in ('name', 'AAPL,phandle')]
    raise SystemExit(f'{path}: no /product node')


def build(seed=None, qemu=False, highmem=False, board='sweet'):
    """qemu=True: same tree, but with QEMU virt's GIC addresses and CNTFRQ."""
    if board not in BOARDS:
        raise SystemExit(f'unknown board {board!r} (choose from {", ".join(BOARDS)})')
    b = BOARDS[board]
    phys_base, mem_size = (b['high_phys_base'], b['high_mem_size']) if highmem else (b['phys_base'], b['mem_size'])
    gicd, gicr, timebase = (QEMU_GICD, QEMU_GICR, QEMU_TIMEBASE) if qemu else (b['gicd'], b['gicr'], b['timebase'])
    vtimer = QEMU_VTIMER_INTID if qemu else b['vtimer']
    seed = seed if seed is not None else os.urandom(64)
    phandle = iter(range(1, 1000))
    ph = lambda: ('AAPL,phandle', u32(next(phandle)))

    chosen = node('chosen', [
        ph(),
        ('dram-base', u64(phys_base)),
        ('dram-size', u64(mem_size)),
        ('random-seed', seed),
        ('debug-enabled', u32(1)),
        ('firmware-version', cstr('sweet-shim')),
        ('system-firmware-version', cstr('sweet-shim')),
        # iBoot's SHA-384 of the boot manifest; /sbin/mount -P 1 exits unless
        # it exists (bind mounts /private/preboot/<hex>/usr/standalone/firmware,
        # tolerating a missing directory). Fixed stand-in value.
        ('boot-manifest-hash', BOOT_MANIFEST_HASH),
        # libimg4 (cryptexd) aborts "failed to get crypto algorithm" without
        # it; real A11+ device trees say sha2-384.
        ('crypto-hash-method', cstr('sha2-384')),
        # MobileGestalt's screen class: display-scale comes from /chosen and
        # the pixel size from IOMobileFramebuffer.  Scale 0 makes SpringBoard's
        # FBSDisplayMode "infxinf@0x" invalid.  The canvas/scale pair must
        # match a real device (sweet: 1125x2436 @3x = 375x812; OP5/8 Plus:
        # 1242x2208 @3x = 414x736).
        ('display-scale', u32(b['display_scale'])),
        # XNU derives IOPlatformUUID (gethostuuid) from these on arm; without
        # them CFPreferences cannot use kCFPreferencesCurrentHost (no ByHost
        # files), so e.g. DataMigration never records LastSystemVersion and
        # migrates on every boot. Synthetic ECID (not the phone's); chip-id
        # of the A11 that the iPhone 8/X userland expects.
        ('unique-chip-id', struct.pack('<Q', SWEET_ECID)),
        ('chip-id', u32(0x8015)),
        # Security status as on a dev-fused, undemoted board (tuple 0,0,1,1):
        # MobileGestalt reads these from /chosen, and mobileactivationd's
        # DeviceType then takes its native "Hactivation" branch (state
        # Activated without an activation record; no SEP, no baseband here).
        ('certificate-production-status', u32(0)),
        ('effective-production-status-ap', u32(0)),
        ('certificate-security-mode', u32(1)),
        ('effective-security-mode-sep', u32(1)),
    ], [node('memory-map', [ph()]),
        # Local boot policy (kern_csr.c): SIP relaxed like `csrutil disable`
        # (lp-sip0: untrusted kexts, unrestricted FS, task_for_pid, kernel
        # debugger, dtrace, nvram), lp-sip1: unauthenticated (unsealed) root.
        # The iOS shared cache is in no trust cache, so dyld can only map it
        # with CSR_ALLOW_UNRESTRICTED_FS (vm_unix.c shared region checks).
        node('asmb', [ph(), ('lp-sip0', u64(0x6f)), ('lp-sip1', u32(1))])])

    # QEMU retains its original single-CPU tree: its MPIDRs differ from the
    # hardware boards.
    cpu_nodes = []
    cpus = [(0, 0, 0, 0, b['cpus'][0][4])] if qemu else b['cpus']
    for core, (mpidr, cluster, cluster_core, l2, hz) in enumerate(cpus):
        cpu_nodes.append(node(f'cpu{core}', [
            ph(),
            ('device_type', cstr('cpu')),
            ('compatible', cstr(b['cpu_compatible']) + cstr('ARM,v8')),
            ('reg', u32(mpidr)),      # actual MPIDR Aff1:Aff0, NOT logical ID
            ('cpu-id', u32(core)),    # descriptive: XNU assigns IDs by DT order
            ('cluster-id', u32(cluster)),
            ('cluster-type', u32(0)),  # homogeneous CLUSTER_TYPE_SMP, not AMP
            ('die-cluster-id', u32(0)),
            ('cluster-core-id', u32(cluster_core)),
            ('l2-cache-id', u32(l2)),
            ('l3-cache-id', u32(0)),   # shared L3
            ('state', cstr('running' if core == 0 else 'stopped')),
            ('timebase-frequency', u32(timebase)),
            ('clock-frequency', u32(hz)),
            ('bus-frequency', u32(100000000)),
            ('memory-frequency', u32(1866000000)),
            ('peripheral-frequency', u32(timebase)),
            ('fixed-frequency', u32(timebase)),
        ]))
    cpus_node = node('cpus', [ph(), ('#address-cells', u32(1)),
                              ('#size-cells', u32(0))], cpu_nodes)

    gic = node('gic', [
        ph(),
        ('compatible', cstr('arm,gic-v3')),
        ('interrupt-controller', b''),
        ('virtual-timer-intid', u32(vtimer)),
        ('reg', u64(gicd - b['soc_base'], b['gicd_size'], gicr - b['soc_base'], b['gicr_size'])),
    ])
    arm_io = node('arm-io', [
        ph(),
        ('device_type', cstr('sweet-io')),
        ('compatible', cstr('sweet-io') + cstr('arm-io')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
        ('ranges', u64(0, b['soc_base'], 0x100000000 - b['soc_base'])),
    ], [gic,
        # No hardware: watchdogd checks IODeviceTree:/arm-io/wdt for no-pmu and
        # otherwise crashes trying to set the PMU boot stage (customer builds
        # ignore the -wdt_no_pmu boot-arg).
        node('wdt', [ph(), ('no-pmu', u32(1))]),
        # Main display: IOMobileFramebuffer.framework counts /arm-io children
        # with this device_type and reads the canvas size from the node
        # (the presented logical size, see SweetFramebuffer.cpp);
        # the kernel's AppleCLCD matches the compatible string.
        node('disp0', [
            ph(),
            ('device_type', cstr('display-subsystem')),
            ('compatible', cstr('sweet,display')),
            ('canvas-width', u32(b['canvas_w'])),
            ('canvas-height', u32(b['canvas_h'])),
        ])])

    fbcon = node('sweet-fbcon', [
        ph(),
        ('reg', u64(b['fb'], b['fb_size'])),
        ('width', u32(b['fb_w'])),
        ('height', u32(b['fb_h'])),
        ('stride', u32(b['fb_stride'])),
    ])

    # bsd/dev/sweet_ufs.c: the UFS host ABL leaves running (absolute physical reg).
    ufs = node('sweet-ufs', [
        ph(),
        ('compatible', cstr('qcom,ufshc')),
        ('reg', u64(b['ufs'], b['ufs_size'])),
    ])

    # pmap_compute_max_asids requires the node even when no overrides are set.
    # An absent pmap-max-asids property selects XNU's own MAX_ASIDS default.
    # No effaceable storage: keybagd then reads /private/var/keybags/systembag.kb
    # as a plain plist instead of decrypting it with the effaceable key.
    defaults = node('defaults', [ph(), ('no-effaceable-storage', u32(1))])

    # MobileGestalt HomeButtonType = IODeviceTree:/buttons home-button-type
    # (iPhone X: 2, no Home button; iPhone 8 Plus: 0/absent = Home button).
    buttons = node('buttons', [
        ph(),
        ('button-names', cstr('volup') + cstr('voldown') + cstr('hold')),
        ('home-button-type', u32(b['home_button_type'])),
        ('opposed-power-vol-buttons', u32(1)),
    ])

    props = product_props(b['product_adt'])
    product = [node('product', [ph()] + props)] if props else []

    # Identity of the iOS device whose userland runs here: compatible[0] is
    # hw.model/hw.target, model is hw.machine/hw.product.
    compat = b''.join(cstr(x) for x in b['compatible'])
    return node('device-tree', [
        ph(),
        ('compatible', compat),
        ('model', cstr(b['model'])),
        ('target-type', cstr(b['target'])),
        ('target-sub-type', cstr(b['target_sub'])),
        ('manufacturer', cstr('Apple Inc.')),
        ('#address-cells', u32(2)),
        ('#size-cells', u32(2)),
    ], [chosen, defaults, cpus_node, arm_io, fbcon, buttons] + product + ([] if qemu else [ufs]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--board', choices=sorted(BOARDS), default='sweet')
    ap.add_argument('--dump', action='store_true')
    ap.add_argument('--qemu', action='store_true')
    ap.add_argument('--highmem', action='store_true')
    args = ap.parse_args()
    root = build(qemu=args.qemu, highmem=args.highmem, board=args.board)
    blob = adt.serialize(root)
    open(args.out, 'wb').write(blob)
    if args.dump:
        adt.dump(adt.parse(blob)[0])
    print(f'{args.out}: {len(blob)} bytes', file=sys.stderr)


if __name__ == '__main__':
    main()
