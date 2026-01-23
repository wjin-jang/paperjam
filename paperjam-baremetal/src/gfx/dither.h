/*
 * PaperJam Bare-Metal OS - Dithering Header
 */

#ifndef DITHER_H
#define DITHER_H

#include "hal/bcm2837.h"

/* Dithering modes */
typedef enum {
    DITHER_BAYER4,
    DITHER_BAYER8,
    DITHER_FLOYD_STEINBERG,
    DITHER_THRESHOLD
} dither_mode_t;

/* Function prototypes */
void dither_bayer4x4(const u8* src, u8* dst, int width, int height);
void dither_bayer8x8(const u8* src, u8* dst, int width, int height);
void dither_floyd_steinberg(const u8* src, u8* dst, int width, int height);
void dither_threshold(const u8* src, u8* dst, int width, int height, u8 threshold);
void dither_scale_and_dither(const u8* src, int src_w, int src_h,
                             u8* dst, int dst_w, int dst_h,
                             dither_mode_t mode);
void dither_draw_to_fb(const u8* gray_src, int src_w, int src_h,
                       int x, int y, dither_mode_t mode);

#endif /* DITHER_H */
