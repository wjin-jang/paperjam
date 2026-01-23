/*
 * FatFS Unicode Support Stub
 *
 * This is a minimal stub. For full Unicode support,
 * use the ffunicode.c from the FatFS distribution.
 */

#include "ff.h"

#if FF_USE_LFN

/* OEM <-> Unicode conversion tables would go here */
/* For ASCII-only, we can use direct mapping */

WCHAR ff_oem2uni(WCHAR oem, WORD cp) {
    (void)cp;
    return oem;  /* Direct mapping for ASCII */
}

WCHAR ff_uni2oem(DWORD uni, WORD cp) {
    (void)cp;
    if (uni > 0x7F) return '?';  /* Non-ASCII -> ? */
    return (WCHAR)uni;
}

DWORD ff_wtoupper(DWORD uni) {
    if (uni >= 'a' && uni <= 'z') {
        return uni - 32;
    }
    return uni;
}

#endif /* FF_USE_LFN */
