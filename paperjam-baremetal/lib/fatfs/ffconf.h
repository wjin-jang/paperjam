/*---------------------------------------------------------------------------/
/  Configurations of FatFs Module R0.16
/---------------------------------------------------------------------------*/

#ifndef FFCONF_DEF
#define FFCONF_DEF	80386	/* Revision ID */

/* Function Configurations */
#define FF_FS_READONLY      0   /* Read/write */
#define FF_FS_MINIMIZE      0   /* Full function */
#define FF_USE_FIND         1   /* Enable f_findfirst/f_findnext */
#define FF_USE_MKFS         0   /* Disable f_mkfs */
#define FF_USE_FASTSEEK     0   /* Disable fast seek */
#define FF_USE_EXPAND       0   /* Disable f_expand */
#define FF_USE_CHMOD        0   /* Disable attribute control */
#define FF_USE_LABEL        0   /* Disable volume label */
#define FF_USE_FORWARD      0   /* Disable f_forward */
#define FF_USE_STRFUNC      1   /* Enable string functions */
#define FF_PRINT_LLI        0   /* No long long printf */
#define FF_PRINT_FLOAT      0   /* No float printf */
#define FF_STRF_ENCODE      3   /* UTF-8 */

/* Locale and Namespace Configurations */
#define FF_CODE_PAGE        437 /* US English */
#define FF_USE_LFN          2   /* Enable LFN with dynamic work buffer on stack */
#define FF_MAX_LFN          255 /* Maximum LFN length */
#define FF_LFN_UNICODE      0   /* ANSI/OEM in API */
#define FF_LFN_BUF          255
#define FF_SFN_BUF          12
#define FF_FS_RPATH         2   /* Enable relative path */

/* Drive/Volume Configurations */
#define FF_VOLUMES          1   /* Number of volumes */
#define FF_STR_VOLUME_ID    0   /* No volume ID strings */
#define FF_MULTI_PARTITION  0   /* Single partition per drive */
#define FF_MIN_SS           512 /* Minimum sector size */
#define FF_MAX_SS           512 /* Maximum sector size */
#define FF_LBA64            0   /* 32-bit LBA */
#define FF_MIN_GPT          0x10000000  /* GPT partition threshold */
#define FF_USE_TRIM         0   /* No TRIM command */

/* System Configurations */
#define FF_FS_TINY          0   /* Normal mode */
#define FF_FS_EXFAT         0   /* No exFAT support */
#define FF_FS_NORTC         1   /* No RTC, use fixed time */
#define FF_NORTC_MON        1   /* Fixed month */
#define FF_NORTC_MDAY       1   /* Fixed day */
#define FF_NORTC_YEAR       2024 /* Fixed year */
#define FF_FS_NOFSINFO      0   /* Use FSINFO */
#define FF_FS_LOCK          0   /* No file lock */
#define FF_FS_REENTRANT     0   /* Not reentrant */

#endif /* FFCONF_H */
