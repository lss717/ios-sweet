/*
 * sweet boot shim entry: arm64 Linux Image header so Qualcomm ABL treats
 * us like a kernel. ABL enters at EL1, MMU/D-cache off, x0 = DTB pointer.
 */
	.section .text.head, "ax"
	.globl _head
_head:
	b	_start			/* code0 */
	.long	0			/* code1 */
	.quad	0			/* text_offset */
	.quad	_end			/* image_size (linked at 0) */
	.quad	0xa			/* flags: LE, 4K pages, place anywhere */
	.quad	0			/* res2 */
	.quad	0			/* res3 */
	.quad	0			/* res4 */
	.ascii	"ARM\x64"		/* magic */
	.long	0			/* res5 (PE offset) */

	.text
	.globl _start
_start:
	msr	daifset, #0xf
	mov	x19, x0			/* DTB pointer from ABL */
	msr	spsel, #1
	adr	x1, _stack_top
	mov	sp, x1
	adr	x1, vectors
	msr	vbar_el1, x1
	isb
	/* zero .bss */
	adr	x1, _bss_start
	adr	x2, _bss_end
1:	cmp	x1, x2
	b.hs	2f
	str	xzr, [x1], #8
	b	1b
2:	mov	x0, x19
	bl	shim_main
3:	wfe
	b	3b

/* PSCI CPU_ON target. x0 = context id = cpu index (1..7). */
	.globl secondary_entry
secondary_entry:
	msr	daifset, #0xf
	msr	spsel, #1
	adr	x1, _sec_stacks
	add	x1, x1, x0, lsl #12
	add	x1, x1, #0x1000
	mov	sp, x1
	adr	x1, vectors
	msr	vbar_el1, x1
	isb
	bl	secondary_main
4:	wfe
	b	4b

/*
 * Entry point for PSCI CPU_ON when XNU is started on a big (Kryo 280) core.
 * x0 = boot_args physical address (PSCI context); the kernel entry physical
 * address is in xnu_boot_tramp_entry.
 */
	.globl xnu_boot_tramp
xnu_boot_tramp:
	msr	daifset, #0xf
	/* Secondary cores may come up at EL2; drop to EL1h first. */
	mrs	x2, currentel
	cmp	x2, #0x8
	b.ne	7f
	mrs	x2, hcr_el2
	mov	x3, #1
	lsl	x3, x3, #31
	orr	x2, x2, x3
	bic	x2, x2, #0x1
	bic	x2, x2, #(1 << 3)
	bic	x2, x2, #(1 << 4)
	bic	x2, x2, #(1 << 5)
	bic	x2, x2, #(1 << 27)
	bic	x2, x2, #(1 << 34)
	msr	hcr_el2, x2
	mov	x3, #3
	msr	cnthctl_el2, x3
	msr	cntvoff_el2, xzr
	mov	x3, #0x3c5
	msr	spsr_el2, x3
	adr	x3, 7f
	msr	elr_el2, x3
	isb
	eret
7:
	mrs	x2, sctlr_el1
	bic	x2, x2, #1		/* MMU off */
	bic	x2, x2, #4		/* D-cache off */
	bic	x2, x2, #(1 << 12)	/* I-cache off */
	msr	sctlr_el1, x2
	isb
	adr	x1, xnu_boot_tramp_entry
	ldr	x1, [x1]
	br	x1

	.data
	.balign	8
	.globl xnu_boot_tramp_entry
xnu_boot_tramp_entry:
	.quad	0

	.text

/*
 * If ABL handed us EL2 (iBoot runs XNU at EL1), drop to EL1h before the
 * kernel entry.  The kernel installs only a VBAR_EL1 and its early writes
 * (OSLAR_EL1) assume EL1.  Returns 1 if it dropped, 0 if already EL1.
 */
	.globl drop_to_el1
drop_to_el1:
	mrs	x1, currentel
	cmp	x1, #0x8
	b.ne	2f
	mrs	x2, hcr_el2
	mov	x3, #1
	lsl	x3, x3, #31
	orr	x2, x2, x3		/* RW=1: EL1 is AArch64 */
	bic	x2, x2, #0x1		/* VM=0: stage 2 off */
	bic	x2, x2, #(1 << 3)	/* FMO=0 */
	bic	x2, x2, #(1 << 4)	/* IMO=0 */
	bic	x2, x2, #(1 << 5)	/* AMO=0 */
	bic	x2, x2, #(1 << 27)	/* TGE=0 */
	bic	x2, x2, #(1 << 34)	/* E2H=0 */
	msr	hcr_el2, x2
	mov	x3, #3			/* EL1PCTEN | EL1PCEN */
	msr	cnthctl_el2, x3
	msr	cntvoff_el2, xzr
	mov	x3, #0x3c5		/* EL1h, DAIF masked */
	msr	spsr_el2, x3
	adr	x3, 1f
	msr	elr_el2, x3
	isb
	eret
1:	mov	x0, #1
	ret
2:	mov	x0, #0
	ret

/*
 * Exception vectors. Each slot stashes x29/x30, loads its slot number
 * and jumps to the common path, which saves x0-x28 and calls
 * exc_handler(slot, regs). IRQs return; everything else ends in the
 * on-screen panic.
 */
.macro vent slot
	.balign	0x80
	stp	x29, x30, [sp, #-16]!
	mov	x29, #\slot
	b	exc_common
.endm

	.balign	0x800
	.globl vectors
vectors:
	vent 0
	vent 1
	vent 2
	vent 3
	vent 4
	vent 5
	vent 6
	vent 7
	vent 8
	vent 9
	vent 10
	vent 11
	vent 12
	vent 13
	vent 14
	vent 15

exc_common:
	sub	sp, sp, #(30 * 8)
	stp	x0, x1, [sp, #0]
	stp	x2, x3, [sp, #16]
	stp	x4, x5, [sp, #32]
	stp	x6, x7, [sp, #48]
	stp	x8, x9, [sp, #64]
	stp	x10, x11, [sp, #80]
	stp	x12, x13, [sp, #96]
	stp	x14, x15, [sp, #112]
	stp	x16, x17, [sp, #128]
	stp	x18, x19, [sp, #144]
	stp	x20, x21, [sp, #160]
	stp	x22, x23, [sp, #176]
	stp	x24, x25, [sp, #192]
	stp	x26, x27, [sp, #208]
	str	x28, [sp, #224]
	mov	x0, x29
	mov	x1, sp
	bl	exc_handler
	ldp	x0, x1, [sp, #0]
	ldp	x2, x3, [sp, #16]
	ldp	x4, x5, [sp, #32]
	ldp	x6, x7, [sp, #48]
	ldp	x8, x9, [sp, #64]
	ldp	x10, x11, [sp, #80]
	ldp	x12, x13, [sp, #96]
	ldp	x14, x15, [sp, #112]
	ldp	x16, x17, [sp, #128]
	ldp	x18, x19, [sp, #144]
	ldp	x20, x21, [sp, #160]
	ldp	x22, x23, [sp, #176]
	ldp	x24, x25, [sp, #192]
	ldp	x26, x27, [sp, #208]
	ldr	x28, [sp, #224]
	add	sp, sp, #(30 * 8)
	ldp	x29, x30, [sp], #16
	eret
