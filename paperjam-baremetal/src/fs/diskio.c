/*
 * PaperJam Bare-Metal OS - FatFS Disk I/O
 *
 * Low-level disk I/O for Chan's FatFS library
 * Connects FatFS to our SD card driver
 */

#include "lib/fatfs/ff.h"
#include "lib/fatfs/diskio.h"
#include "hal/mmc.h"
#include "hal/timer.h"

/* Drive number for SD card */
#define DEV_SD      0

/*
 * Get disk status
 */
DSTATUS disk_status(BYTE pdrv) {
    if (pdrv != DEV_SD) {
        return STA_NOINIT;
    }

    if (!mmc_is_initialized()) {
        return STA_NOINIT;
    }

    return 0;
}

/*
 * Initialize disk
 */
DSTATUS disk_initialize(BYTE pdrv) {
    if (pdrv != DEV_SD) {
        return STA_NOINIT;
    }

    if (mmc_init() < 0) {
        return STA_NOINIT;
    }

    return 0;
}

/*
 * Read sectors
 */
DRESULT disk_read(BYTE pdrv, BYTE* buff, LBA_t sector, UINT count) {
    if (pdrv != DEV_SD) {
        return RES_PARERR;
    }

    if (!mmc_is_initialized()) {
        return RES_NOTRDY;
    }

    if (mmc_read_blocks((u32)sector, buff, count) < 0) {
        return RES_ERROR;
    }

    return RES_OK;
}

/*
 * Write sectors
 */
DRESULT disk_write(BYTE pdrv, const BYTE* buff, LBA_t sector, UINT count) {
    if (pdrv != DEV_SD) {
        return RES_PARERR;
    }

    if (!mmc_is_initialized()) {
        return RES_NOTRDY;
    }

    if (mmc_write_blocks((u32)sector, buff, count) < 0) {
        return RES_ERROR;
    }

    return RES_OK;
}

/*
 * Disk I/O control
 */
DRESULT disk_ioctl(BYTE pdrv, BYTE cmd, void* buff) {
    if (pdrv != DEV_SD) {
        return RES_PARERR;
    }

    if (!mmc_is_initialized()) {
        return RES_NOTRDY;
    }

    switch (cmd) {
        case CTRL_SYNC:
            /* No-op, we don't have write caching */
            return RES_OK;

        case GET_SECTOR_COUNT:
            /* Return a large number - we don't know the actual size */
            *(LBA_t*)buff = 0x1000000;  /* 8GB in 512-byte sectors */
            return RES_OK;

        case GET_SECTOR_SIZE:
            *(WORD*)buff = MMC_BLOCK_SIZE;
            return RES_OK;

        case GET_BLOCK_SIZE:
            *(DWORD*)buff = 1;  /* Erase block size in sectors */
            return RES_OK;

        default:
            return RES_PARERR;
    }
}

/*
 * Get current time for FAT timestamps
 */
DWORD get_fattime(void) {
    /* Return a fixed timestamp (2024-01-01 00:00:00) */
    /* We don't have RTC, so this is just a placeholder */
    return ((DWORD)(2024 - 1980) << 25) |   /* Year */
           ((DWORD)1 << 21) |                /* Month */
           ((DWORD)1 << 16) |                /* Day */
           ((DWORD)0 << 11) |                /* Hour */
           ((DWORD)0 << 5) |                 /* Minute */
           ((DWORD)0 >> 1);                  /* Second */
}
