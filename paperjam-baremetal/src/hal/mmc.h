/*
 * PaperJam Bare-Metal OS - MMC/SD Card Driver Header
 */

#ifndef MMC_H
#define MMC_H

#include "bcm2837.h"

/* Block size */
#define MMC_BLOCK_SIZE      512

/* Function prototypes */
int  mmc_init(void);
int  mmc_read_block(u32 lba, u8* buffer);
int  mmc_write_block(u32 lba, const u8* buffer);
int  mmc_read_blocks(u32 lba, u8* buffer, u32 count);
int  mmc_write_blocks(u32 lba, const u8* buffer, u32 count);
int  mmc_is_initialized(void);
int  mmc_is_sdhc(void);

#endif /* MMC_H */
