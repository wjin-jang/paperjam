/*
 * FatFS Stub Implementation
 *
 * NOTE: This is a minimal stub for compilation purposes.
 * For actual use, download the complete FatFS library from:
 * http://elm-chan.org/fsw/ff/
 *
 * Replace this file with the real ff.c from FatFS.
 */

#include "ff.h"
#include "diskio.h"

/* Minimal implementation stubs */

static FATFS* mounted_fs = NULL;

FRESULT f_mount(FATFS* fs, const TCHAR* path, BYTE opt) {
    (void)path;

    if (fs == NULL) {
        mounted_fs = NULL;
        return FR_OK;
    }

    if (opt) {
        /* Immediate mount - initialize disk */
        if (disk_initialize(0) != 0) {
            return FR_NOT_READY;
        }
    }

    mounted_fs = fs;
    fs->fs_type = 1;  /* Assume FAT */
    fs->pdrv = 0;

    return FR_OK;
}

FRESULT f_open(FIL* fp, const TCHAR* path, BYTE mode) {
    if (!mounted_fs) return FR_NOT_ENABLED;
    if (!fp || !path) return FR_INVALID_PARAMETER;

    fp->fs = mounted_fs;
    fp->flag = mode;
    fp->err = 0;
    fp->fptr = 0;
    fp->obj_size = 0;

    /* TODO: Implement actual file open logic */
    /* This requires parsing FAT directory entries */

    return FR_NO_FILE;  /* Stub: always fails */
}

FRESULT f_close(FIL* fp) {
    if (!fp) return FR_INVALID_OBJECT;
    fp->fs = NULL;
    return FR_OK;
}

FRESULT f_read(FIL* fp, void* buff, UINT btr, UINT* br) {
    if (!fp || !fp->fs) return FR_INVALID_OBJECT;
    if (!buff) return FR_INVALID_PARAMETER;

    *br = 0;

    /* TODO: Implement actual read logic */

    return FR_OK;
}

FRESULT f_write(FIL* fp, const void* buff, UINT btw, UINT* bw) {
    if (!fp || !fp->fs) return FR_INVALID_OBJECT;
    if (!buff) return FR_INVALID_PARAMETER;

    *bw = 0;

    /* TODO: Implement actual write logic */

    return FR_OK;
}

FRESULT f_lseek(FIL* fp, DWORD ofs) {
    if (!fp || !fp->fs) return FR_INVALID_OBJECT;

    if (ofs > fp->obj_size) {
        fp->fptr = fp->obj_size;
    } else {
        fp->fptr = ofs;
    }

    return FR_OK;
}

FRESULT f_opendir(DIR* dp, const TCHAR* path) {
    if (!mounted_fs) return FR_NOT_ENABLED;
    if (!dp || !path) return FR_INVALID_PARAMETER;

    dp->fs = mounted_fs;
    dp->index = 0;

    /* TODO: Implement directory open logic */

    return FR_OK;
}

FRESULT f_closedir(DIR* dp) {
    if (!dp) return FR_INVALID_OBJECT;
    dp->fs = NULL;
    return FR_OK;
}

FRESULT f_readdir(DIR* dp, FILINFO* fno) {
    if (!dp || !dp->fs) return FR_INVALID_OBJECT;

    if (fno) {
        /* Clear file info - indicates end of directory */
        fno->fname[0] = 0;
    }

    /* TODO: Implement directory read logic */

    return FR_OK;
}

FRESULT f_stat(const TCHAR* path, FILINFO* fno) {
    if (!mounted_fs) return FR_NOT_ENABLED;
    if (!path) return FR_INVALID_PARAMETER;

    /* TODO: Implement stat logic */

    return FR_NO_FILE;
}

FRESULT f_mkdir(const TCHAR* path) {
    if (!mounted_fs) return FR_NOT_ENABLED;
    if (!path) return FR_INVALID_PARAMETER;

    /* TODO: Implement mkdir logic */

    return FR_OK;  /* Silently succeed for stub */
}

FRESULT f_unlink(const TCHAR* path) {
    if (!mounted_fs) return FR_NOT_ENABLED;
    if (!path) return FR_INVALID_PARAMETER;

    /* TODO: Implement unlink logic */

    return FR_OK;
}

FRESULT f_rename(const TCHAR* path_old, const TCHAR* path_new) {
    (void)path_old;
    (void)path_new;
    return FR_OK;
}

FRESULT f_sync(FIL* fp) {
    (void)fp;
    return FR_OK;
}

FRESULT f_truncate(FIL* fp) {
    (void)fp;
    return FR_OK;
}

FRESULT f_findfirst(DIR* dp, FILINFO* fno, const TCHAR* path, const TCHAR* pattern) {
    FRESULT res = f_opendir(dp, path);
    if (res != FR_OK) return res;

    dp->pat = pattern;
    return f_findnext(dp, fno);
}

FRESULT f_findnext(DIR* dp, FILINFO* fno) {
    return f_readdir(dp, fno);
}

TCHAR* f_gets(TCHAR* buff, int len, FIL* fp) {
    if (!fp || !fp->fs || !buff || len < 1) return NULL;

    int i = 0;
    UINT br;
    TCHAR c;

    while (i < len - 1) {
        if (f_read(fp, &c, 1, &br) != FR_OK || br == 0) {
            break;
        }
        buff[i++] = c;
        if (c == '\n') break;
    }

    buff[i] = 0;
    return (i > 0) ? buff : NULL;
}

int f_putc(TCHAR c, FIL* fp) {
    UINT bw;
    if (f_write(fp, &c, 1, &bw) != FR_OK || bw != 1) {
        return -1;
    }
    return c;
}

int f_puts(const TCHAR* str, FIL* fp) {
    int n = 0;
    while (*str) {
        if (f_putc(*str++, fp) < 0) return -1;
        n++;
    }
    return n;
}

/*
 * NOTE: This stub implementation is NOT functional.
 *
 * To make this work, you need to:
 * 1. Download FatFS from http://elm-chan.org/fsw/ff/
 * 2. Replace this file with the real ff.c
 * 3. The diskio.c in src/fs/ provides the low-level disk I/O
 *
 * The real FatFS handles:
 * - FAT12/FAT16/FAT32 filesystem parsing
 * - Directory traversal
 * - File allocation table management
 * - Long filename support
 * - Unicode support
 */
