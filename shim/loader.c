/*
 * Milestone 4: act as iBoot for xnu.
 *
 * mkpayload.py already resolved the kernel's chained fixups and built the
 * ADT, so this only has to: find the payload in the ABL ramdisk, copy the
 * segments to phys_base + (vmaddr - virt_base), place the ADT and
 * boot_args behind the kernel, and jump to the entry point with the MMU
 * and caches off, x0 = boot_args (physical).
 */
#include <stdint.h>
#include "console.h"
#include "fdt.h"
#include "loader.h"

#define BOOT_LINE_LENGTH	608
#define PAGE_16K		0x4000UL

struct payload_seg {
	uint64_t vmaddr, vmsize, file_off, file_size;
};

struct payload {
	char magic[8];
	uint32_t version, nsegs;
	uint64_t virt_base, entry_va, adt_off, adt_size, kernel_end;
	uint64_t phys_base, mem_size;
	char cmdline[BOOT_LINE_LENGTH];
	struct payload_seg segs[];
};

/* pexpert/pexpert/arm64/boot.h, Revision/Version 2 */
struct boot_video {
	uint64_t v_baseAddr, v_display, v_rowBytes, v_width, v_height, v_depth;
};

struct boot_args {
	uint16_t Revision, Version;
	uint64_t virtBase, physBase, memSize, topOfKernelData;
	struct boot_video Video;
	uint32_t machineType;
	uint64_t deviceTreeP;
	uint32_t deviceTreeLength;
	char CommandLine[BOOT_LINE_LENGTH];
	uint64_t bootFlags, memSizeActual;
};

_Static_assert(__builtin_offsetof(struct payload, segs) == 0x2a8, "payload header layout");
_Static_assert(__builtin_offsetof(struct boot_args, Video) == 40, "boot_args layout");
_Static_assert(__builtin_offsetof(struct boot_args, CommandLine) == 108, "boot_args layout");
_Static_assert(sizeof(struct boot_args) == 736, "boot_args layout");

/* MMU off: everything is Device memory, so copy in aligned 8-byte words. */
static void copy64(uintptr_t dst, uintptr_t src, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	volatile const uint64_t *s = (volatile const uint64_t *)src;
	for (uint64_t i = 0; i < (n + 7) / 8; i++)
		d[i] = s[i];
}

static void zero64(uintptr_t dst, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	for (uint64_t i = 0; i < n / 8; i++)
		d[i] = 0;
}

/*
 * The ABL on the OP5 leaves the MMU and the D-cache on, so our copies may
 * still be dirty in cache when we hand over with caches off.  Push them out.
 */
static void clean_dcache(uintptr_t start, uintptr_t end)
{
	for (uintptr_t a = start & ~(uintptr_t)63; a < end; a += 64)
		__asm__ volatile("dc civac, %0" :: "r"(a) : "memory");
	__asm__ volatile("dsb sy" ::: "memory");
}

static int magic_ok(const char *m)
{
	static const char want[] = "SWEETXNU";
	for (int i = 0; i < 8; i++)
		if (m[i] != want[i])
			return 0;
	return 1;
}

typedef void (*xnu_entry_t)(uint64_t boot_args_pa);

const char *loader_boot(uintptr_t dtb)
{
	uint64_t rd_start, rd_end;

	if (!fdt_chosen_u64(dtb, "linux,initrd-start", &rd_start) ||
	    !fdt_chosen_u64(dtb, "linux,initrd-end", &rd_end))
		return "no initrd in /chosen";
	con_hex2("INITRD", "lo=", rd_start, "hi=", rd_end);

	const struct payload *p = (const struct payload *)rd_start;
	if (!magic_ok(p->magic))
		return "no SWEETXNU payload";
	if (p->version != 1 || (p->adt_off & 7) || (rd_start & 7))
		return "bad payload header";

	uint64_t pa_of_va_base = p->phys_base - p->virt_base;	/* pa = va + this */
	con_hex2("PHYS", "base=", p->phys_base, "size=", p->mem_size);
	con_hex("VIRT", p->virt_base);
	con_hex("ENTRY", p->entry_va);

	/* The payload must not overlap where the kernel goes. */
	if (rd_end > p->phys_base && rd_start < p->phys_base + p->mem_size)
		return "ramdisk overlaps kernel memory";

	for (uint32_t i = 0; i < p->nsegs; i++) {
		const struct payload_seg *s = &p->segs[i];
		uintptr_t dst = s->vmaddr + pa_of_va_base;
		copy64(dst, rd_start + s->file_off, s->file_size);
		if (s->vmsize > s->file_size)
			zero64(dst + ((s->file_size + 7) & ~7UL), s->vmsize - ((s->file_size + 7) & ~7UL));
	}
	con_hex2("SEGS", "n=", p->nsegs, "end=", p->kernel_end + pa_of_va_base);

	/* ADT, then boot_args, behind the kernel; everything below topOfKernelData is ours. */
	uintptr_t adt_pa = p->kernel_end + pa_of_va_base;
	copy64(adt_pa, rd_start + p->adt_off, p->adt_size);
	uintptr_t ba_pa = (adt_pa + p->adt_size + PAGE_16K - 1) & ~(PAGE_16K - 1);
	uintptr_t top = ba_pa + PAGE_16K;

	zero64(ba_pa, PAGE_16K);
	volatile struct boot_args *ba = (volatile struct boot_args *)ba_pa;
	ba->Revision = 2;
	ba->Version = 2;
	ba->virtBase = p->virt_base;
	ba->physBase = p->phys_base;
	ba->memSize = p->mem_size;
	ba->topOfKernelData = top;
	ba->Video.v_baseAddr = FB_BASE;
	ba->Video.v_display = 1;
	ba->Video.v_rowBytes = FB_STRIDE;
	ba->Video.v_width = FB_W;
	ba->Video.v_height = FB_H;
	ba->Video.v_depth = 32;
	ba->deviceTreeP = adt_pa - pa_of_va_base;	/* xnu reads it with the MMU on: a VA */
	ba->deviceTreeLength = (uint32_t)p->adt_size;
	for (int i = 0; i < BOOT_LINE_LENGTH; i++)
		ba->CommandLine[i] = p->cmdline[i];
	ba->memSizeActual = p->mem_size;
	con_hex2("BOOTARG", "pa=", ba_pa, "top=", top);

	clean_dcache(p->phys_base, top);

	uintptr_t entry_pa = p->entry_va + pa_of_va_base;
	con_hex("JUMP", entry_pa);
	con_str("XNU", "jumping (fbcon clears screen)");

	uint64_t sctlr0;
	__asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr0));

#ifdef SHIM_DIAG
	{
		extern uint64_t drop_to_el1(void);
		extern volatile uint64_t diag_sctlr, diag_ttbr0, diag_tcr;
		uint64_t el0, ttbr0, tcr;
		__asm__ volatile("mrs %0, currentel" : "=r"(el0));
		__asm__ volatile("mrs %0, ttbr0_el1" : "=r"(ttbr0));
		__asm__ volatile("mrs %0, tcr_el1" : "=r"(tcr));
		diag_sctlr = sctlr0;
		diag_ttbr0 = ttbr0;
		diag_tcr = tcr;
		con_hex2("EL", "cur=", (uint32_t)(el0 >> 2),
			 "drop=", (uint32_t)drop_to_el1());
		con_hex2("S0", "lo=", (uint32_t)(sctlr0 & 0xff), "x", 0);
		con_hex2("TTBR0", "pa=", (uint32_t)ttbr0,
			 "hi=", (uint32_t)(ttbr0 >> 32));
	}
#endif

	/*
	 * The OnePlus 5 ABL hands off with the MMU ON (sweet's leaves it off).
	 * XNU's start.s uses PC-relative adrp results as physical addresses, so
	 * it must be entered with translation disabled; otherwise its first
	 * bootstrap-pagetable access faults into its own "b ." vector.
	 */
	if (sctlr0 & 1) {
		uint64_t off = sctlr0 & ~(uint64_t)((1u << 0) | (1u << 2) | (1u << 12));
		__asm__ volatile("msr sctlr_el1, %0" :: "r"(off) : "memory");
		__asm__ volatile("isb; ic iallu; dsb sy; isb" ::: "memory");
	}

#ifdef SHIM_DIAG
	{
		uint64_t sctlr1;
		__asm__ volatile("mrs %0, sctlr_el1" : "=r"(sctlr1));
		con_hex2("S1", "lo=", (uint32_t)(sctlr1 & 0xff), "x", 0);
	}
#endif

#ifdef SHIM_BIGBOOT
	/*
	 * Kryo 280's A53 cluster has no 16KB granule (ID_AA64MMFR0.TGran16=0)
	 * but the A73-derived big cores do, so start XNU on CPU4 (0x100).
	 */
	{
		extern void xnu_boot_tramp(void);
		extern volatile uint64_t xnu_boot_tramp_entry;
		extern int64_t shim_psci_cpu_on(uint64_t, uint64_t, uint64_t);
		extern void shim_delay_ms(unsigned);
		int64_t rc;

		xnu_boot_tramp_entry = entry_pa;
		clean_dcache((uintptr_t)&xnu_boot_tramp_entry,
			     (uintptr_t)&xnu_boot_tramp_entry + 64);
		con_hex2("BIG", "mpidr=", (uint32_t)0x100, "a", 0);
		for (int i = 0; i < 6; i++) {
			rc = shim_psci_cpu_on(0x100, (uintptr_t)xnu_boot_tramp,
					      ba_pa);
			if (rc == 0)
				break;
			shim_delay_ms(300);
		}
		con_hex2("BIG", "rc=", (uint32_t)rc, "a", 0);
		if (rc != 0) {
			extern void shim_reset(unsigned);
			shim_delay_ms(60000);
			shim_reset(10);
		}
		for (;;)
			__asm__ volatile("wfe");
	}
#endif

	/* Everything was written with the MMU and caches off; drop any stale I-cache lines too. */
	__asm__ volatile("dsb sy; ic iallu; dsb sy; isb" ::: "memory");
	((xnu_entry_t)entry_pa)(ba_pa);
	return "xnu returned";
}
