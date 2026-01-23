/*
 * FatFS Header (Stub)
 *
 * Note: This is a minimal stub header. For actual use, you would include
 * the complete FatFS library from http://elm-chan.org/fsw/ff/
 *
 * This stub provides type definitions and function declarations.
 */

#ifndef FF_H
#define FF_H

#include <stdint.h>

/* Configuration */
#include "ffconf.h"

/* Integer types */
typedef unsigned char   BYTE;
typedef unsigned short  WORD;
typedef unsigned long   DWORD;
typedef uint32_t        LBA_t;
typedef unsigned int    UINT;
typedef char            TCHAR;

/* File function return code (FRESULT) */
typedef enum {
    FR_OK = 0,              /* Succeeded */
    FR_DISK_ERR,            /* A hard error occurred */
    FR_INT_ERR,             /* Assertion failed */
    FR_NOT_READY,           /* Physical drive not ready */
    FR_NO_FILE,             /* Could not find the file */
    FR_NO_PATH,             /* Could not find the path */
    FR_INVALID_NAME,        /* The path name format is invalid */
    FR_DENIED,              /* Access denied */
    FR_EXIST,               /* Access denied */
    FR_INVALID_OBJECT,      /* Invalid file/directory object */
    FR_WRITE_PROTECTED,     /* Physical drive is write protected */
    FR_INVALID_DRIVE,       /* Invalid drive number */
    FR_NOT_ENABLED,         /* Volume has no work area */
    FR_NO_FILESYSTEM,       /* No valid FAT volume */
    FR_MKFS_ABORTED,        /* f_mkfs() aborted */
    FR_TIMEOUT,             /* Timeout */
    FR_LOCKED,              /* File is locked */
    FR_NOT_ENOUGH_CORE,     /* Not enough memory */
    FR_TOO_MANY_OPEN_FILES, /* Too many open files */
    FR_INVALID_PARAMETER    /* Invalid parameter */
} FRESULT;

/* File access mode and open method flags */
#define FA_READ             0x01
#define FA_WRITE            0x02
#define FA_OPEN_EXISTING    0x00
#define FA_CREATE_NEW       0x04
#define FA_CREATE_ALWAYS    0x08
#define FA_OPEN_ALWAYS      0x10
#define FA_OPEN_APPEND      0x30

/* File attribute bits */
#define AM_RDO  0x01    /* Read only */
#define AM_HID  0x02    /* Hidden */
#define AM_SYS  0x04    /* System */
#define AM_DIR  0x10    /* Directory */
#define AM_ARC  0x20    /* Archive */

/* Filesystem object structure (FATFS) */
typedef struct {
    BYTE    fs_type;        /* Filesystem type */
    BYTE    pdrv;           /* Physical drive number */
    BYTE    n_fats;         /* Number of FATs */
    BYTE    wflag;          /* Win[] flag */
    BYTE    fsi_flag;       /* FSINFO flags */
    WORD    id;             /* Volume mount ID */
    WORD    n_rootdir;      /* Number of root directory entries */
    WORD    csize;          /* Cluster size [sectors] */
    DWORD   last_clst;      /* Last allocated cluster */
    DWORD   free_clst;      /* Number of free clusters */
    DWORD   n_fatent;       /* Number of FAT entries */
    DWORD   fsize;          /* Size of a FAT [sectors] */
    LBA_t   volbase;        /* Volume base sector */
    LBA_t   fatbase;        /* FAT base sector */
    LBA_t   dirbase;        /* Root directory base sector/cluster */
    LBA_t   database;       /* Data base sector */
    LBA_t   winsect;        /* Current sector in win[] */
    BYTE    win[512];       /* Disk access window */
} FATFS;

/* File object structure (FIL) */
typedef struct {
    FATFS*  fs;             /* Pointer to filesystem object */
    WORD    id;             /* Volume mount ID */
    BYTE    flag;           /* Status flags */
    BYTE    err;            /* Abort flag */
    DWORD   fptr;           /* File read/write pointer */
    DWORD   obj_size;       /* File size */
    DWORD   sclust;         /* File start cluster */
    DWORD   clust;          /* Current cluster */
    LBA_t   sect;           /* Current sector */
    LBA_t   dir_sect;       /* Sector of directory entry */
    BYTE*   dir_ptr;        /* Pointer to directory entry */
    DWORD   dir_clst;       /* Cluster of directory entry */
    BYTE    buf[512];       /* File private buffer */
} FIL;

/* Directory object structure (DIR) */
typedef struct {
    FATFS*  fs;             /* Pointer to filesystem */
    WORD    id;             /* Volume mount ID */
    WORD    index;          /* Current index */
    DWORD   sclust;         /* Start cluster */
    DWORD   clust;          /* Current cluster */
    LBA_t   sect;           /* Current sector */
    BYTE*   dir;            /* Pointer to current entry */
    BYTE    fn[12];         /* SFN buffer */
#if FF_USE_LFN
    DWORD   blk_ofs;        /* Offset of LFN entry block */
#endif
#if FF_USE_FIND
    const TCHAR* pat;       /* Pattern to match */
#endif
} DIR;

/* File information structure (FILINFO) */
typedef struct {
    DWORD   fsize;          /* File size */
    WORD    fdate;          /* Modified date */
    WORD    ftime;          /* Modified time */
    BYTE    fattrib;        /* File attribute */
#if FF_USE_LFN
    TCHAR   altname[13];    /* Alternative file name */
    TCHAR   fname[FF_MAX_LFN + 1];  /* Primary file name */
#else
    TCHAR   fname[13];      /* File name */
#endif
} FILINFO;

/* FatFS module application interface */
FRESULT f_open(FIL* fp, const TCHAR* path, BYTE mode);
FRESULT f_close(FIL* fp);
FRESULT f_read(FIL* fp, void* buff, UINT btr, UINT* br);
FRESULT f_write(FIL* fp, const void* buff, UINT btw, UINT* bw);
FRESULT f_lseek(FIL* fp, DWORD ofs);
FRESULT f_truncate(FIL* fp);
FRESULT f_sync(FIL* fp);
FRESULT f_opendir(DIR* dp, const TCHAR* path);
FRESULT f_closedir(DIR* dp);
FRESULT f_readdir(DIR* dp, FILINFO* fno);
FRESULT f_findfirst(DIR* dp, FILINFO* fno, const TCHAR* path, const TCHAR* pattern);
FRESULT f_findnext(DIR* dp, FILINFO* fno);
FRESULT f_mkdir(const TCHAR* path);
FRESULT f_unlink(const TCHAR* path);
FRESULT f_rename(const TCHAR* path_old, const TCHAR* path_new);
FRESULT f_stat(const TCHAR* path, FILINFO* fno);
FRESULT f_chmod(const TCHAR* path, BYTE attr, BYTE mask);
FRESULT f_utime(const TCHAR* path, const FILINFO* fno);
FRESULT f_chdir(const TCHAR* path);
FRESULT f_chdrive(const TCHAR* path);
FRESULT f_getcwd(TCHAR* buff, UINT len);
FRESULT f_getfree(const TCHAR* path, DWORD* nclst, FATFS** fatfs);
FRESULT f_getlabel(const TCHAR* path, TCHAR* label, DWORD* vsn);
FRESULT f_setlabel(const TCHAR* label);
FRESULT f_forward(FIL* fp, UINT(*func)(const BYTE*,UINT), UINT btf, UINT* bf);
FRESULT f_expand(FIL* fp, DWORD fsz, BYTE opt);
FRESULT f_mount(FATFS* fs, const TCHAR* path, BYTE opt);
FRESULT f_mkfs(const TCHAR* path, BYTE opt, DWORD au, void* work, UINT len);

int f_putc(TCHAR c, FIL* fp);
int f_puts(const TCHAR* str, FIL* cp);
int f_printf(FIL* fp, const TCHAR* str, ...);
TCHAR* f_gets(TCHAR* buff, int len, FIL* fp);

#define f_eof(fp) ((int)((fp)->fptr == (fp)->obj_size))
#define f_error(fp) ((fp)->err)
#define f_tell(fp) ((fp)->fptr)
#define f_size(fp) ((fp)->obj_size)
#define f_rewind(fp) f_lseek((fp), 0)
#define f_rewinddir(dp) f_readdir((dp), 0)
#define f_rmdir(path) f_unlink(path)
#define f_unmount(path) f_mount(0, path, 0)

#endif /* FF_H */
