/*
 * FatFS Disk I/O Header
 */

#ifndef DISKIO_H
#define DISKIO_H

#include "ff.h"

/* Status of Disk Functions */
typedef BYTE DSTATUS;

/* Results of Disk Functions */
typedef enum {
    RES_OK = 0,     /* Successful */
    RES_ERROR,      /* R/W Error */
    RES_WRPRT,      /* Write Protected */
    RES_NOTRDY,     /* Not Ready */
    RES_PARERR      /* Invalid Parameter */
} DRESULT;

/* Disk Status Bits */
#define STA_NOINIT      0x01    /* Drive not initialized */
#define STA_NODISK      0x02    /* No medium in the drive */
#define STA_PROTECT     0x04    /* Write protected */

/* Command code for disk_ioctl function */
#define CTRL_SYNC           0   /* Complete pending write process */
#define GET_SECTOR_COUNT    1   /* Get media size */
#define GET_SECTOR_SIZE     2   /* Get sector size */
#define GET_BLOCK_SIZE      3   /* Get erase block size */
#define CTRL_TRIM           4   /* Trim data block */

/* Function prototypes */
DSTATUS disk_initialize(BYTE pdrv);
DSTATUS disk_status(BYTE pdrv);
DRESULT disk_read(BYTE pdrv, BYTE* buff, LBA_t sector, UINT count);
DRESULT disk_write(BYTE pdrv, const BYTE* buff, LBA_t sector, UINT count);
DRESULT disk_ioctl(BYTE pdrv, BYTE cmd, void* buff);
DWORD get_fattime(void);

#endif /* DISKIO_H */
