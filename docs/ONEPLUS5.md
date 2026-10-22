# OnePlus 5 (cheeseburger) iOS 16 bring-up plan

Status: A line (shim) paused 2026-10-22 - XNU booted on the Kryo 280 cores up
to `bsd_init`, then stopped at `IOKitInitializeTime`; the project moved to the
**B line** (UEFI + UniXNU, 4K pages), which reaches the kernel entry and now
hangs in MMU enable.  See `NOTES.md` (top section) for the current state.
Target date: 2026-10-20
Base project: `ios-sweet` (XNU 8796 / iOS 16.7.16 userland on Qualcomm hardware)

## 1. Goal and confirmed decisions

Run the unmodified iOS 16.7.16 (20H392) userland of the **iPhone 8 Plus**
(`D21AP` / `iPhone10,2`) on a **OnePlus 5** (`cheeseburger`, Qualcomm
MSM8998 / Snapdragon 835), booting through `fastboot boot` of our shim and
using a writable HFS+ root in the internal `userdata` partition.

Confirmed by the device owner:

| Item | Decision |
| --- | --- |
| Device | OnePlus 5 (cheeseburger), **8 GB RAM / 128 GB storage** |
| Bootloader | Already unlocked |
| Userland | **iPhone 8 Plus**, iOS 16.7.16 (20H392), `D21AP` / `iPhone10,2` |
| `userdata` | May be erased and replaced with the iOS HFS+ root |
| Host | Existing Linux workstation |
| Preserved | bootloader, recovery, modem, persist, fsg/fsc and all partition backups |
| Boot method | Temporary `fastboot boot`; nothing is flashed to the boot partitions |

The iPhone 8 Plus userland is chosen over iPhone X because the OP5 panel is
native 1080x1920 (16:9). iPhone X is 1125x2436 (19.5:9); the current
`SweetFramebuffer` presents the logical size 1:1 and crops it, so an X userland
would lose about 258 px at the top and bottom. The 8 Plus mode is
1242x2208 @3x (414x736 points), downsampled by the real device to its
1080x1920 panel; our virtual display has to do the same.

## 0. Progress (2026-10-20, A line - superseded by the B line)

> This section describes the original shim route (A line), which is paused
> since 2026-10-22.  Current state and next action: `NOTES.md`, top section.

Done locally:

- Linux tooling installed under `~/.local` (no root): Android platform-tools
  (`adb`, `fastboot`), AOSP `mkbootimg`/`unpack_bootimg`, and `ipsw`.
- `shim/` now has a board profile (`shim/board.h`); `BOARD=op5` compiles and
  renders a 1080x1920 host console instead of sweet's 1080x2400.
- `tools/mkadt.py --board op5` generates the OP5 ADT with the 4+4 MPIDR list,
  1080x1920 panel / 1242x2208 canvas, MSM8998 GIC/UFS/framebuffer addresses,
  and the real D21AP `/product` node. The iPhone 8 Plus device tree was
  extracted to `research/ipsw-x/d21ap.adt` (gitignored).
- `tools/repack_bootv0.py` repacks a v0/v1 stock boot image.  The OP5 stock
  image is **not QCDT**: its kernel is `Image.gz` with 20 appended DTBs inside
  the kernel section.  The tool copies that DTB tail after the new gzip kernel
  and can trim the all-zero partition padding.
- `xnu/patches/0082-op5-machine-config.patch` adds the `OP5` machine config
  (ARMv8.0 compile flags, Kryo 280 MPIDR validation, platform/CPU matches);
  the staging scripts now also run for `OP5`.
- `python3 tools/validate-repo.py` passes with 82 patches (the OP5 patch
  applies after 0081; the sweet-specific branches remain unchanged).

The preparation commit is `52fb90b` and has been pushed to
`lss717/ios-sweet`.  The repository is a fork and GitHub Actions has not run
yet (no workflow runs are visible); enable Actions in the fork settings and
dispatch `xnu.yml` with `machine_config=OP5` to verify the OP5 build.  The
default push build is still `SWEET`, which checks that the new patch applies
and does not regress sweet.

M0 done on the phone (2026-10-21):

- Booted TWRP 3.4.0-1 temporarily and pulled `boot`, `recovery`, `persist`,
  `modemst1/2`, `fsg`, `fsc` to `backup/op5/` (gitignored).  `userdata` is
  `/dev/block/sda13`, 121560084480 bytes.
- Stock `boot.img`: header v0, page 4096, kernel 21533041 bytes starting with
  gzip, ramdisk 1297198, no QCDT magic, 20 FDTs appended inside the kernel
  section, followed by all-zero 64 MB partition padding.  TWRP has the same
  layout with 7 appended DTBs.
- `fastboot boot` occasionally returns `Failed to load/authenticate boot
  image: 00000050` after a USB re-enumeration, but succeeds after re-entering
  the bootloader.  Do not treat one failure as a permanent restriction.

M1 PASSED on hardware (2026-10-21 ~00:20 local):

- Image: `shim/out/shim-boot-op5-M1-verified.img` (SHA256
  `e5b9ff8bf4...a71d589`), built as gzip shim + stock DTB tail, trimmed.
- `fastboot boot` returned OKAY; the panel showed:
  `SHIM op5 milestone 4: xnu loader`, `INITRD ...`, `LOADER no SWEETXNU
  payload`, then `UFS milestone 5 probe (read-only)`.
- UFS: `ver=00000210`, host enabled/ready, TUR/CAP/READ all `rc=00000000`,
  `LUN0 lastlba=01C627F? blk=00001000`, GPT `EFI PART`, `entries=00000020`,
  `cache` and `userdata` ext4.  This proves ABL leaves the UFS host and the
  framebuffer usable on the OP5.
- The raw (non-gzip) shim did not boot; OP5 ABL needs `Image.gz + DTB tail`.

M2 kernel build PASSED (2026-10-21):

- Actions enabled on `lss717/ios-sweet`; `xnu.yml` dispatched with
  `machine_config=OP5`, run **39546720041** succeeded (7m15s).
- Kernel `xnu/out-op5/kernel.development.op5`, Mach-O arm64, sha256
  `41d25054...b750`; contains `Kryo 280`, `oneplus,cheeseburger` and the
  open-source asm/pmap.
- Build fixes: OP5 early framebuffer (`0x9d600000`, 1080x1920), the
  libpthread/BearSSL Makefile conditions now match `SWEET OP5`, and
  `config/MASTER.arm64.op5` (patch 0083) stops `doconf -soc op5` from using
  the generic config.
- M2 payload/image built, not booted (no hardware this session):
  `shim/out/payload-op5-M2.bin` and `shim/out/shim-boot-op5-M2.img`
  (sha256 `dce93bc4...500e`; boot args `cpus=1 ... ufsroot=cache` are inside
  the payload ADT, not in the boot header cmdline).

Host migration (2026-10-21): the project moved to `ls@192.168.10.127`
(Ubuntu 24.04, x86_64), which is now the **only active host**; the WSL/USBIPD
machine is retired and no longer used.  All gitignored artifacts and tooling
were copied and hash-verified.  This host has the real `hfsplus` kernel module,
so the mini root was built there: `shim/out/op5-root-mini.img` (128 MiB,
`fsck` OK) with `/sbin/launchd` = the static init.

Verified on 2026-10-21 (no hardware action):

- `main` = `origin/main` = `b091e62`, clean tree, `tools/validate-repo.py`
  passes (83 patches).
- CI `39546720041` (OP5) is the newest run and it succeeded; nothing newer.
- M2 image: header v0, gzip shim kernel, ramdisk byte-identical to the
  payload; kernel arguments come from the ADT in the payload, not from the
  boot header cmdline.
- Mini root `fsck` OK; the static init is present intact at offset `0x202000`.

Not done yet:

- M2 boot on hardware (UFS root + launchd) and `cpus=8`.
- Attach the phone to 127, confirm the `cache` partition size
  (`blockdev --getsize64 /dev/block/by-name/cache` in TWRP; the image is
  128 MiB), flash the mini root to `cache`, then boot the M2 image.
- M3 prerequisites: `apfs-fuse` is not installed on 127 (needs
  `sudo apt install apfs-fuse`) and the iPhone 8 Plus 20H392 IPSW is not
  downloaded yet.

This is a bring-up plan, not a usable daily phone OS. The same limitations as
sweet apply: no GPU, Wi-Fi, Bluetooth, cellular, audio, camera, sensors,
GPS, SEP or App Store.

## 2. Hardware facts used by the port

Derived from the downstream MSM8998/cheeseburger device trees in
`LineageOS/android_kernel_oneplus_msm8998` branch `lineage-18.1`
(`msm8998.dtsi`, `msm8998-blsp.dtsi`, `msm8998-mtp.dtsi`,
`cheeseburger.dtsi`, `cheeseburger-pvt.dtsi`).

| Area | OnePlus 5 | Note |
| --- | --- | --- |
| SoC | MSM8998 / Snapdragon 835, ARMv8.0-A | **No ARMv8.1 LSE atomics** |
| CPU | 4x Cortex-A53 at MPIDR `0x0-0x3`, 4x Cortex-A73 at `0x100-0x103` | two clusters, 4+4 |
| GIC | GICD `0x17a00000`; GICR `0x17b00000`, stride `0x20000`, 8 redistributors | sweet uses GICR `0x17a60000` |
| Timer | 19.2 MHz, virtual timer INTID 19, physical 18 | same as sweet |
| UFS | `ufshc@1da4000`, UFS PHY `0x1da7000`, UFS ICE `0x1db0000` | sweet uses `0x1d84000` |
| Splash framebuffer | `cont_splash_mem` `0x9d600000`, size `0x02400000` (36 MiB) | verify stride on hardware |
| PSHOLD | `0x010ac000` | sweet uses `0x0c264000` |
| IMEM | `0x146bf000`; `restart_reason@65c` -> `0x146bf65c` | sweet uses `0x146aa65c` |
| SPMI arbiter | core `0x800f000`, channels `0x8400000`, observer `0x9400000`, interrupt `0xa400000`, config `0x800a000` | SM7150 addresses differ |
| PMIC | PM8998 (SID 0), PMI8998 (SID 2/3) | power/reset via PON `0x800` |
| Volume keys | vol+ PM8998 GPIO6, vol- PM8998 GPIO5 | power/reset via PON |
| Home | fingerprint module (FPC1020 / Goodix), not in PM8998 `gpio_keys` | first version must synthesize Home |
| Touch | Synaptics S3320 (RMI4), I2C address `0x20` | sweet uses Goodix GT9896 |
| Touch bus | BLSP1 QUP5 I2C `0xc179000`, 400 kHz, IRQ 99, TLMM 87/88 | no GENI on MSM8998 |
| Touch GPIO | reset TLMM 89, IRQ TLMM 125 | |
| Touch rails | PM8998 L6 (1.8 V), L28 (2.8 V) | 835 uses **RPM**, not RPMh |
| Display | Samsung S6E3FA3/5/6, 1080x1920 AMOLED, single DSI | 5.5", 401 ppi |
| USB | DWC3 `0xa800000`, QUSB2 PHY `0xc012000` | later milestone only |
| Battery | PMI8998 fuel gauge / bq27541 on I2C7 `0xc1b5000` at `0x55` | first version uses a stub |
| Storage | UFS 2.1, 128 GB; `userdata` holds the iOS root | 16 GB HFS+ image is enough |

Measured on the device through the B line (2026-10-22, UEFI payload
`CheeseburgerInfo`): RAM 8 GB (7039 MiB usable / 51 descriptors), UFS logical
block **4096 B** (not 512 B), main LUN 29,763,584 blocks = 116,264 MiB, GOP
framebuffer `0x9D400000` 1080x1920 stride 1080 BGRX (`0x7E9000` bytes),
`userdata` `first_lba 0x14F40` / `last_lba 0x1C627FA` = 115,928 MiB, no A/B
slots, `hw-revision 20001`.  The firmware memory map has a hole at
`0x17A000000-0x180000000`: do not place the kernel window there.

### 8 GB memory layout

MSM8998 8 GB devices normally expose:

- low bank: `0x80000000` .. `0x100000000` (2 GB, contains all fixed carve-outs)
- high bank: `0x100000000` .. `0x280000000` (6 GB)

Start conservatively with `HIGH_PHYS_BASE = 0x100000000` and
`HIGH_MEM_SIZE = 0xfcc00000` (~3.95 GiB), which is known to avoid the
Qualcomm XPU carve-outs on sweet. After the live OP5 FDT is available, the
usable high-bank size can be expanded toward 6 GiB.

The 128 GB `userdata` partition is flashed with a 16 GB HFS+ image; the
remaining space is untouched, and the 4 MiB persistent-log ring lives at the
end of the whole partition (same scheme as sweet).

## 3. Overall strategy

1. Work on branch `op5-bringup`; keep the existing sweet build green.
2. Add a distinct `OP5` machine configuration (or a `SWEET_OP5` variant) with
   **ARMv8.0 compile flags**. The current sweet build uses
   `-march=armv8.2-a+crypto` (`xnu/patches/0004-sweet-machine-config.patch:18`);
   Kryo 280 does not implement the ARMv8.1 LSE atomics, so a v8.2 kernel can
   die with SIGILL immediately. Use `-march=armv8-a` for the first version.
3. Prefer ADT-provided addresses over new hard-coded constants where practical;
   for the first bring-up, OP5 constants are acceptable.
4. Do not proceed to iOS userland until the shim proves that ABL leaves both
   the UFS host and the display framebuffer usable.
5. One commit per milestone, with results, CI run IDs and unfinished work
   recorded in `NOTES.md`.

### Build tree changes

| File / area | Change |
| --- | --- |
| `makedefs/MakeInc.def` | add `OP5` to supported configs and define its flags |
| `pexpert/pexpert/arm64/OP5.h` | board header (copy the SWEET shape, ARMv8.0) |
| `osfmk/arm64/proc_reg.h` | 64-byte cache lines for Kryo 280 |
| `xnu/patches/0019|0020|0026` staging scripts | also stage libpthread/BearSSL/HFS for OP5 |
| `.github/workflows/xnu.yml` | allow `machine_config=OP5` |
| `shim/` | OP5 constants and boot-image v0 packaging |
| `tools/mkadt.py` | OP5 board profile and D21AP identity |
| `xnu/patches/0082-op5-*.patch` | board/driver changes |

## 4. Milestones

### M0 - Preparation, backups, boot-format verification

No kernel changes yet.

- Confirm the device is an OnePlus 5 (cheeseburger), not a 5T (dumpling), and
  record the current OxygenOS/firmware version.
- Back up outside the repository: `boot`, `dtbo`, `vbmeta`, `persist`,
  `modemst1`, `modemst2`, `fsg`, `fsc`, `recovery`. Never commit dumps,
  serial numbers or Apple artifacts.  With the phone in TWRP:
  `tools/op5-pull-stock.sh backup/op5`.
- Pull the stock `boot.img` and inspect it with `unpack_bootimg`:
  - boot header version (confirmed v0 on this device);
  - the DTB layout (confirmed: gzip kernel + appended DTBs, no QCDT);
  - kernel/ramdisk base and offsets.
  The current `shim/build.sh` produces a **boot header v2** image for sweet;
  OP5 needs a **v0 image with `Image.gz + appended DTBs`** instead.  The raw
  shim Image alone does not boot.
- Verify that the unlocked bootloader accepts an unsigned temporary image, for
  example by booting TWRP with `fastboot boot twrp.img` (do not flash it).
- Confirm `/dev/block/by-name/userdata` exists in recovery and record its size.
- Host tools: `aarch64-linux-gnu-gcc`, `mkbootimg`/`unpack_bootimg`,
  `dtbtool` or `mkqcdtbootimg`, `apfs-fuse`, `hfsprogs`, `rsync`,
  `img2simg`/`simg2img`, `gh`, `ipsw`, `python3`.  On 127 everything is
  present except **`apfs-fuse`** (needed for M3, not yet installed).

Exit criteria: stock boot format and DTB packaging are understood; backups
are verified; `fastboot boot` is known to work.

### M1 - Shim, console, GIC/timer and UFS probe

Goal: prove that ABL leaves the UFS host and the splash framebuffer usable.

Files and constants:

| File | Change |
| --- | --- |
| `shim/console.h:4-7` | `FB_BASE 0x9d600000`, 1080x1920, stride 4320 (verify) |
| `shim/mmu.h:4` | `FB_PHYS 0x9d600000` |
| `shim/shim.c:15-20` | `IMEM 0x146bf65c`, `PSHOLD 0x010ac000` |
| `shim/shim.c:19-20` | `GICD 0x17a00000`, `GICR 0x17b00000` |
| `shim/shim.c:33` | virtual timer INTID 19 (same) |
| `shim/shim.c` PSCI probe | CPU_ON targets `0x0,0x1,0x2,0x3,0x100..0x103` |
| `shim/ufs.c:14` | `UFS_BASE 0x1da4000` |
| `shim/build.sh` | `BOARD=op5`; v0 repack, gzip shim + stock DTB tail |
| `tools/mkadt.py` | `--board op5` profile, initial constants only |

ADT profile for M1:

- `PHYS_BASE 0x100000000`, `MEM_SIZE 0xfcc00000`
- `SOC_BASE 0x01000000` (keep nonzero)
- `FB 0x9d600000`, `FB_SIZE 0x02400000`, 1080x1920, stride 4320
- `UFS 0x1da4000`, size `0x3000`
- CPU nodes 0-7 with `reg = [0,1,2,3,0x100,0x101,0x102,0x103]`

Build a probe image with no XNU payload and boot it with `fastboot boot`.

Exit criteria:

- `SHIM` banner and GIC/timer output on the panel;
- UFS probe finds the GPT and the `userdata` partition;
- screen is not skewed (if it is, adjust stride: 4320/4352/4608);
- console is readable over the panel.

If the UFS host is not alive or the framebuffer is not where the downstream DT
says, stop and investigate ABL hand-off before continuing.

### M2 - XNU early boot, UFS root, launchd

- Add the OP5 machine config and stage the same open-source dependencies as
  sweet (libpthread, HFS, BearSSL).
- Extend `SweetCPU` validity: the current sweet check accepts only MPIDRs with
  Aff0=0, but OP5 uses `0x101`, `0x102`, `0x103`.
- Start with `cpus=1`, then `cpus=4` (A53 cluster), then `cpus=8`.
  First boot treats all cores as one homogeneous cluster; AMP/P-E cluster
  types are a later optimization.
- Make the platform expert match `oneplus,cheeseburger` / `qcom,msm8998` (or
  keep the existing sweet match internally, but document it).
- `sweet_ufs.c`: base `0x1da4000`, or read the base from the `sweet-ufs` ADT
  node. GPT lookup stays `ufsroot=userdata`.
- ADT identity: `D21AP`, `iPhone10,2`, `target-type D21`, `/product` copied
  from the real D21AP device tree, `/buttons` copied from the real tree,
  `display-scale=3`, canvas 1242x2208.
- Boot a minimal root (or the current small test image) with `rd=ufsroot0`.

Expected log lines:

```
SWEET UFS: "userdata" ...
BSD root: ufsroot0
hfs: mounted ...
*** SWEET userspace: init running as PID 1 ***
exec launchd
```

Persistent log: `tools/sweet-log-pull.sh:25` already resolves
`by-name/userdata`, so it should work unchanged in OP5 TWRP.

Exit criteria: launchd runs from the OP5 UFS; persistent log can be pulled
after a boot.

### M3 - Display and iOS GUI (iPhone 8 Plus)

- Download the iPhone 8 Plus iOS 16.7.16 (20H392) IPSW, extract OS, SystemOS
  and AppOS, then build the 16 GB HFS+ image with `tools/mkiosroot.sh` and
  apply `tools/sweet-root-tweaks.py`.
- The root tweaks are device-agnostic (they find containers by identifier and
  patch every MediaToolbox `SubServerConfiguration.plist`), so the existing
  Setup skip, activation seed, watchdog and audio workarounds should carry
  over.
- `SweetFramebuffer.cpp`:
  - panel 1080x1920;
  - logical canvas 1242x2208 at scale 3 (414x736 points);
  - add a CPU downscaler from 1242x2208 to 1080x1920; the current code copies
    1:1 and centers, which is only correct for iPhone X on sweet;
  - dot pitch 401;
  - `sweetfb_noconsole=1`, `sweetfb_hz=30`.
- Verify the FBSDisplayMode against the real 8 Plus mode. Do not present
  1080x1920 with scale 3: that becomes the nonexistent 360x640 class and can
  trigger SpringBoard's "No status bar visual provider" path.
- Flash the root image to `userdata` only after explicit confirmation.

Exit criteria: lock screen, home screen, Settings and Control Center appear;
screenshots or photos are captured and stored outside git.

### M4 - Input

Keys:

- Port `sweet_keys.c` to the MSM8998 SPMI arbiter:
  core `0x800f000`, observer `0x9400000`, config `0x800a000`.
- PM8998 SID 0: PON `0x800` (power/resin), GPIO 6 (vol+), GPIO 5 (vol-).
- Map power, volume up/down to HID consumer keys.

Home:

- OP5's Home/fingerprint is handled by the FPC1020 or Goodix module, not by the
  PM8998 `gpio_keys`.
- First version: synthesize a Home button event from the kernel (for example a
  long volume-down press or a boot argument) so the 8 Plus UI can return to the
  home screen.
- Later: a minimal fingerprint/Home driver if the physical button is wanted.

Touch:

- Write a minimal BLSP I2C driver for `0xc179000` (400 kHz, TLMM 87/88).
- Synaptics S3320 uses RMI4; implement the minimum:
  - F01 device control;
  - F11 2D absolute reporting;
  - reset GPIO 89 and IRQ GPIO 125;
  - no firmware update, no gestures.
- Check whether PM8998 L6/L28 are already on from ABL by probing address
  `0x20`. If they are off, an RPM/SMD regulator vote is required (835 uses
  RPM, not RPMh); this is the largest input-side risk.
- Map touch coordinates 1080x1920 to the 1242x2208 logical canvas.

Exit criteria: touch, power and volume work in Setup/SpringBoard; Home returns
to the home screen; the device can be unlocked and navigated.

### M5 - Polish

- SMP: keep 8 cores homogeneous first, then optionally expose 4+4 cluster
  types to the scheduler.
- Battery: static `IOPMPowerSource` first, then PMI8998 FG / bq27541.
- Display refresh rate, UFS batching, crash-report symbolication.
- USB device mode and live log over USB (DWC3 `0xa800000`, QUSB2 PHY
  `0xc012000`) if needed.
- Expect the same app-level gaps as sweet (Phone/Photos/Messages black,
  no App Store, no Apple ID).

## 5. Verification commands

Build a boot image for kernel K and ADT A:

```sh
python3 tools/mkadt.py --board op5 shim/out/op5.adt --highmem
python3 tools/mkpayload.py "$K" shim/out/op5.adt shim/out/payload-op5.bin \
    --cmdline 'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam \
    -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 \
    wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 \
    sweetfb_noconsole=1 sweetfb_hz=30'
(cd shim && ./build.sh ../shim/out/payload-op5.bin)
cp shim/out/shim-boot.img shim/out/shim-boot-op5-M1.img
```

Boot:

```sh
fastboot boot shim/out/shim-boot-op5-M1.img
```

Read the persistent log from TWRP:

```sh
fastboot boot twrp.img
tools/sweet-log-pull.sh logs/op5-M2.txt
adb reboot bootloader
```

Kernel-side checkpoints:

| Milestone | Expected |
| --- | --- |
| M1 | `SHIM`, GIC/timer counts, `UFS: "userdata"`, no panic |
| M2 | `BSD root: ufsroot0`, `hfs: mounted`, `launchd` PID 1 |
| M3 | iOS lock screen / home screen on the panel |
| M4 | touch taps move the UI; power/volume/Home events arrive |

## 6. Risk register

| Risk | Severity | Mitigation |
| --- | --- | --- |
| ABL does not leave the UFS host initialized | High | Probe first; if dead, implement UFS PHY/clock init |
| Splash framebuffer address or stride differs | High | Probe live FDT; try 0x9d600000/0x9c000000 and 4320/4352/4608 |
| ARMv8.0 vs current v8.2 code generation | High | OP5 machine config with `-march=armv8-a`; check ESR/ELR on SIGILL |
| Touch rails are off and require RPM | High | Probe `0x20` first; implement minimal RPM vote only if needed |
| Synaptics RMI4 driver | Medium-high | Start with F01/F11 only |
| v0 `Image.gz` + appended-DTB packaging | Medium | `repack_bootv0.py --trim` (verified on M1) |
| 8 Plus canvas/scale mismatch | Medium | Use 1242x2208 @3x and add downscaling; validate FBSDisplayMode |
| 4+4 cluster handling | Medium | Homogeneous 8-core first, AMP later |
| No SEP/Touch ID | Low-medium | Same stub approach as Face ID; no passcode |
| OP5 firmware variance | Medium | Record the exact firmware; verify the live FDT before trusting constants |

## 7. Next concrete action

The project is on the **B line** (UEFI + UniXNU, 4K pages) since 2026-10-22;
the A line (shim + payload ADT) is paused.  Full state: `NOTES.md`, top
section; B-line repositories: `~/UniXNU`, `~/UniXNU-cheeseburger`,
`~/edk2-msm8998`.

**B line (current):**

1. Attach the phone to 127 and enter fastboot (`adb reboot bootloader` from
   Android, otherwise Power+VolDown); `fastboot devices` must list it.
2. `fastboot boot /home/ls/UniXNU-cheeseburger/out/cheeseburger/boot/boot-physbase.img`
   (sha256 `4847be5f…6b49`; carries the DarwinBoot `VirtBase`/`PhysicalBase`
   fix, payload `payload-stage3b.img` `1d1b8fd4…7934`).
3. A fourth early colour band -> the MMU is through; swap in the panic
   kernel (`payload-ci.img`) and continue.  Still three bands -> inspect
   TTBR/TCR (stage 4 probe `_set_mmu_ttb`) or isolate the kernel in QEMU.

**A line (paused fallback):**

4. `fastboot boot shim/out/shim-boot-op5-bigcore-bigadt.img` (sha256
   `fe5c7c97…1d37`) - never booted.  It tests the `os_log`/firehose theory
   behind the `IOKitInitializeTime` stop.  The mini HFS root
   (`shim/out/op5-root-mini.img`) is already flashed to `cache`.
5. For M3/M4, build the iPhone 8 Plus 20H392 root image (needs `apfs-fuse`:
   `sudo apt install apfs-fuse`, route A) or the iPad7,1 17.7.11 4K fixture
   (route B, already cached in `~/UniXNU/out/ipsw/21H461/`).

## 8. Open items

- Exact OxygenOS/firmware version currently installed on the device.
- B line: pass MMU enable (`PhysicalBase` fix compiled, not booted); explain
  `owned=0` in DarwinBoot; then panic-free userland bring-up.
- A line: verify `shim-boot-op5-bigcore-bigadt.img` (never booted).
- Firmware memory hole `0x17A000000-0x180000000` is not usable for the kernel
  window.
- UFS 4096 B logical blocks (measured); driver paths must not assume 512 B.
- M3 tooling on 127: `apfs-fuse` missing (`sudo apt install apfs-fuse`) and
  the iPhone 8 Plus 20H392 IPSW not downloaded; route B uses the cached
  iPad7,1 17.7.11 fixture instead.
- Confirm whether PM8998 L6/L28 are on before the touch driver is written.
- Touch/display/keys are still M3/M4 work.

## 8.1 Local commands used

```sh
export PATH="$HOME/.local/bin:$PATH"

# 1. Extract the real iPhone 8 Plus /product tree (Apple artifact; gitignored)
python3 tools/remotezip.py <IPSW_URL> DeviceTree.d21ap.im4p research/ipsw-x/dt
ipsw img4 im4p extract research/ipsw-x/dt/Firmware/all_flash/DeviceTree.d21ap.im4p \
    -o research/ipsw-x/d21ap.adt

# 2. Generate the OP5 ADT
python3 tools/mkadt.py shim/out/op5.adt --board op5 --highmem

# 3. Compile the shim without packaging
BOARD=op5 PACKAGE=0 ./shim/build.sh

# 4. Package with a pulled stock boot.img (v0, gzip + appended DTBs)
BOARD=op5 OP5_BOOT_TEMPLATE=backup/op5/boot.img ./shim/build.sh shim/out/payload-op5.bin
```

## 9. References

- Downstream device tree: `LineageOS/android_kernel_oneplus_msm8998`,
  branch `lineage-18.1` (`msm8998.dtsi`, `msm8998-blsp.dtsi`,
  `msm8998-mtp.dtsi`, `cheeseburger.dtsi`, `cheeseburger-pvt.dtsi`).
- `NOTES.md` - sweet bring-up history and the working hardware/software
  techniques this plan reuses.
- `README.md` - build, flash and log workflows.
