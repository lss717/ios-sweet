#pragma once
#include <stdint.h>

/*
 * Board-specific constants for the shim.  Select with -DBOARD_OP5; the
 * default is the original Redmi Note 10 Pro (sweet) profile.
 */
#if defined(BOARD_OP5)

#define BOARD_NAME	"op5"
#define BOARD_DESC	"OnePlus 5 (MSM8998)"

/* ABL continuous-splash framebuffer (msm8998 cont_splash_mem). */
#define FB_BASE		0x9d600000UL
#define FB_W		1080
#define FB_H		1920
#define FB_STRIDE	(FB_W * 4)

/* GICv3: same distributor as sweet, different redistributor base. */
#define GICD_BASE	0x17a00000UL
#define GICR_BASE	0x17b00000UL
#define GICR_SIZE	0x100000UL
#define VTIMER_INTID	19
#define PTIMER_INTID	18

/* MSM8998 IMEM / PSHOLD. */
#define IMEM_RESTART_REASON	0x146bf65cUL
#define PSHOLD			0x010ac000UL

/* UFS host left enabled by ABL (ufshc@1da4000). */
#define UFS_BASE	0x01da4000UL
#define UFS_SIZE	0x3000UL

#else /* sweet */

#define BOARD_NAME	"sweet"
#define BOARD_DESC	"Redmi Note 10 Pro (SM7150)"

#define FB_BASE		0x9c000000UL
#define FB_W		1080
#define FB_H		2400
#define FB_STRIDE	(FB_W * 4)

#define GICD_BASE	0x17a00000UL
#define GICR_BASE	0x17a60000UL
#define GICR_SIZE	0x100000UL
#define VTIMER_INTID	19
#define PTIMER_INTID	18

#define IMEM_RESTART_REASON	0x146aa65cUL
#define PSHOLD			0x0c264000UL

#define UFS_BASE	0x01d84000UL
#define UFS_SIZE	0x3000UL

#endif

#define FB_PHYS		FB_BASE

static inline uint64_t
board_cpu_mpidr(unsigned int i)
{
#if defined(BOARD_OP5)
	/* 4x Cortex-A53 (cluster 0), 4x Cortex-A73 (cluster 1). */
	static const uint64_t ids[8] = {
		0x0, 0x1, 0x2, 0x3, 0x100, 0x101, 0x102, 0x103
	};
#else
	/* sweet puts each core in MPIDR Aff1. */
	static const uint64_t ids[8] = {
		0x0, 0x100, 0x200, 0x300, 0x400, 0x500, 0x600, 0x700
	};
#endif
	return i < 8 ? ids[i] : 0;
}
