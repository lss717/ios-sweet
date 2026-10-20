# OnePlus 5 (cheeseburger) iOS 16 bring-up plan

Status: M0 tooling + M1 software prepared; device boot pending
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

## 0. Progress (2026-10-20)

Done locally:

- Linux tooling installed under `~/.local` (no root): Android platform-tools
  (`adb`, `fastboot`), AOSP `mkbootimg`/`unpack_bootimg`, and `ipsw`.
- `shim/` now has a board profile (`shim/board.h`); `BOARD=op5` compiles and
  renders a 1080x1920 host console instead of sweet's 1080x2400.
- `tools/mkadt.py --board op5` generates the OP5 ADT with the 4+4 MPIDR list,
  1080x1920 panel / 1242x2208 canvas, MSM8998 GIC/UFS/framebuffer addresses,
  and the real D21AP `/product` node. The iPhone 8 Plus device tree was
  extracted to `research/ipsw-x/d21ap.adt` (gitignored).
- `tools/repack_bootv0.py` repacks a v0/v1 stock boot image, preserving its
  QCDT tail; a round-trip test verified kernel/ramdisk replacement and QCDT
  preservation.
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

Not done yet (blocked on the phone):

- No device is currently attached (`adb devices` is empty), so the stock
  `boot.img` has not been inspected and no M1 probe image has been booted.
- Partition backups, TWRP check and the actual `fastboot boot` test remain.

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
  serial numbers or Apple artifacts.
- Pull the stock `boot.img` and inspect it with `unpack_bootimg`:
  - boot header version (expected v0 for a 2017 device);
  - whether the DTB is a QCDT table or a separate blob;
  - kernel/ramdisk base and offsets.
  The current `shim/build.sh` produces a **boot header v2** image for sweet;
  OP5 will very likely need a v0 + QCDT image instead.
- Verify that the unlocked bootloader accepts an unsigned temporary image, for
  example by booting TWRP with `fastboot boot twrp.img` (do not flash it).
- Confirm `/dev/block/by-name/userdata` exists in recovery and record its size.
- Host tools: `aarch64-linux-gnu-gcc`, `mkbootimg`/`unpack_bootimg`,
  `dtbtool` or `mkqcdtbootimg`, `apfs-fuse`, `hfsprogs`, `rsync`,
  `img2simg`/`simg2img`, `gh`, `ipsw`, `python3`.

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
| `shim/build.sh` | `BOARD=op5`; v0/QCDT repack using the stock boot.img |
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
| Boot header v0/QCDT packaging | Medium | Inspect stock boot.img and reproduce it exactly |
| 8 Plus canvas/scale mismatch | Medium | Use 1242x2208 @3x and add downscaling; validate FBSDisplayMode |
| 4+4 cluster handling | Medium | Homogeneous 8-core first, AMP later |
| No SEP/Touch ID | Low-medium | Same stub approach as Face ID; no passcode |
| OP5 firmware variance | Medium | Record the exact firmware; verify the live FDT before trusting constants |

## 7. Next concrete action

1. Connect the OP5 with USB debugging / fastboot and verify it appears in
   `adb devices` or `fastboot devices`.
2. Boot TWRP temporarily and back up the partitions listed in M0. Pull the
   stock `boot.img` and run `unpack_bootimg` on it.
3. Record the header version, QCDT layout, kernel/ramdisk addresses and DTB;
   adjust `tools/repack_bootv0.py` if the stock image differs from the
   synthetic round-trip test.
4. Build and boot the M1 probe image:
   `BOARD=op5 PACKAGE=0 ./shim/build.sh` for the compile check, then
   `BOARD=op5 OP5_BOOT_TEMPLATE=backup/op5/boot.img ./shim/build.sh` for the
   bootable image.

## 8. Open items

- Exact OxygenOS/firmware version currently installed on the device.
- Stock `boot.img` / TWRP image for cheeseburger; neither is in the repo.
- Confirm whether `fastboot boot` is accepted by this bootloader/firmware.
- Confirm the panel framebuffer address/stride left by the OP5 ABL (M1 probe).
- Confirm whether PM8998 L6/L28 are on before the touch driver is written.
- Expand the 8 GB high-bank size after the live FDT is available.

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

# 4. Package with a pulled stock boot.img (v0/QCDT template)
BOARD=op5 OP5_BOOT_TEMPLATE=backup/op5/boot.img ./shim/build.sh shim/out/payload-op5.bin
```

## 9. References

- Downstream device tree: `LineageOS/android_kernel_oneplus_msm8998`,
  branch `lineage-18.1` (`msm8998.dtsi`, `msm8998-blsp.dtsi`,
  `msm8998-mtp.dtsi`, `cheeseburger.dtsi`, `cheeseburger-pvt.dtsi`).
- `NOTES.md` - sweet bring-up history and the working hardware/software
  techniques this plan reuses.
- `README.md` - build, flash and log workflows.
