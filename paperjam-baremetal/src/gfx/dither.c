/*
 * PaperJam Bare-Metal OS - Dithering for Album Art
 *
 * Implements Bayer 4x4 ordered dithering for converting
 * grayscale images to 1-bit for e-paper display
 */

#include "hal/bcm2837.h"
#include "dither.h"
#include "framebuffer.h"
#include "sys/heap.h"

/* Bayer 4x4 dithering matrix (normalized to 0-15) */
static const u8 bayer_4x4[4][4] = {
    {  0,  8,  2, 10 },
    { 12,  4, 14,  6 },
    {  3, 11,  1,  9 },
    { 15,  7, 13,  5 }
};

/* Bayer 8x8 dithering matrix (normalized to 0-63) */
static const u8 bayer_8x8[8][8] = {
    {  0, 32,  8, 40,  2, 34, 10, 42 },
    { 48, 16, 56, 24, 50, 18, 58, 26 },
    { 12, 44,  4, 36, 14, 46,  6, 38 },
    { 60, 28, 52, 20, 62, 30, 54, 22 },
    {  3, 35, 11, 43,  1, 33,  9, 41 },
    { 51, 19, 59, 27, 49, 17, 57, 25 },
    { 15, 47,  7, 39, 13, 45,  5, 37 },
    { 63, 31, 55, 23, 61, 29, 53, 21 }
};

/*
 * Dither 8-bit grayscale image to 1-bit using Bayer 4x4
 * src: source grayscale image (0=black, 255=white)
 * dst: destination 1-bit image (packed, 8 pixels per byte)
 */
void dither_bayer4x4(const u8* src, u8* dst, int width, int height) {
    int dst_row_bytes = (width + 7) / 8;

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            u8 gray = src[y * width + x];

            /* Apply Bayer threshold */
            int threshold = bayer_4x4[y & 3][x & 3] * 16;  /* Scale to 0-240 */
            int pixel = (gray > threshold) ? 1 : 0;

            /* Set bit in output */
            int byte_idx = y * dst_row_bytes + (x / 8);
            int bit_idx = 7 - (x % 8);

            if (pixel) {
                dst[byte_idx] |= (1 << bit_idx);
            } else {
                dst[byte_idx] &= ~(1 << bit_idx);
            }
        }
    }
}

/*
 * Dither using Bayer 8x8 matrix (better quality)
 */
void dither_bayer8x8(const u8* src, u8* dst, int width, int height) {
    int dst_row_bytes = (width + 7) / 8;

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            u8 gray = src[y * width + x];

            /* Apply Bayer threshold */
            int threshold = bayer_8x8[y & 7][x & 7] * 4;  /* Scale to 0-252 */
            int pixel = (gray > threshold) ? 1 : 0;

            int byte_idx = y * dst_row_bytes + (x / 8);
            int bit_idx = 7 - (x % 8);

            if (pixel) {
                dst[byte_idx] |= (1 << bit_idx);
            } else {
                dst[byte_idx] &= ~(1 << bit_idx);
            }
        }
    }
}

/*
 * Floyd-Steinberg error diffusion dithering
 * Higher quality but slower than ordered dithering
 */
void dither_floyd_steinberg(const u8* src, u8* dst, int width, int height) {
    int dst_row_bytes = (width + 7) / 8;

    /* Error buffer (need two rows) */
    i16* error = (i16*)heap_alloc(width * 2 * sizeof(i16));
    if (!error) {
        /* Fall back to simple threshold */
        dither_threshold(src, dst, width, height, 128);
        return;
    }

    i16* error_curr = error;
    i16* error_next = error + width;
    memset(error, 0, width * 2 * sizeof(i16));

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            /* Get pixel with accumulated error */
            int old_pixel = src[y * width + x] + error_curr[x];
            if (old_pixel < 0) old_pixel = 0;
            if (old_pixel > 255) old_pixel = 255;

            /* Quantize */
            int new_pixel = (old_pixel > 127) ? 255 : 0;
            int quant_error = old_pixel - new_pixel;

            /* Output pixel */
            int byte_idx = y * dst_row_bytes + (x / 8);
            int bit_idx = 7 - (x % 8);

            if (new_pixel) {
                dst[byte_idx] |= (1 << bit_idx);
            } else {
                dst[byte_idx] &= ~(1 << bit_idx);
            }

            /* Distribute error */
            if (x + 1 < width) {
                error_curr[x + 1] += quant_error * 7 / 16;
            }
            if (y + 1 < height) {
                if (x > 0) {
                    error_next[x - 1] += quant_error * 3 / 16;
                }
                error_next[x] += quant_error * 5 / 16;
                if (x + 1 < width) {
                    error_next[x + 1] += quant_error * 1 / 16;
                }
            }
        }

        /* Swap error buffers */
        i16* temp = error_curr;
        error_curr = error_next;
        error_next = temp;
        memset(error_next, 0, width * sizeof(i16));
    }

    heap_free(error);
}

/*
 * Simple threshold dithering
 */
void dither_threshold(const u8* src, u8* dst, int width, int height, u8 threshold) {
    int dst_row_bytes = (width + 7) / 8;

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int pixel = (src[y * width + x] > threshold) ? 1 : 0;

            int byte_idx = y * dst_row_bytes + (x / 8);
            int bit_idx = 7 - (x % 8);

            if (pixel) {
                dst[byte_idx] |= (1 << bit_idx);
            } else {
                dst[byte_idx] &= ~(1 << bit_idx);
            }
        }
    }
}

/*
 * Scale and dither grayscale image to fit display area
 * Uses nearest-neighbor scaling
 */
void dither_scale_and_dither(const u8* src, int src_w, int src_h,
                             u8* dst, int dst_w, int dst_h,
                             dither_mode_t mode) {
    /* Calculate scaled dimensions maintaining aspect ratio */
    int scale_w = dst_w * 256 / src_w;
    int scale_h = dst_h * 256 / src_h;
    int scale = (scale_w < scale_h) ? scale_w : scale_h;

    int out_w = src_w * scale / 256;
    int out_h = src_h * scale / 256;

    /* Center in destination */
    int offset_x = (dst_w - out_w) / 2;
    int offset_y = (dst_h - out_h) / 2;

    /* Allocate scaled grayscale buffer */
    u8* scaled = (u8*)heap_alloc(dst_w * dst_h);
    if (!scaled) return;

    /* Clear to white */
    memset(scaled, 255, dst_w * dst_h);

    /* Scale with nearest-neighbor */
    for (int y = 0; y < out_h; y++) {
        int src_y = y * src_h / out_h;
        for (int x = 0; x < out_w; x++) {
            int src_x = x * src_w / out_w;
            scaled[(offset_y + y) * dst_w + (offset_x + x)] =
                src[src_y * src_w + src_x];
        }
    }

    /* Dither */
    int dst_bytes = ((dst_w + 7) / 8) * dst_h;
    memset(dst, 0xFF, dst_bytes);

    switch (mode) {
        case DITHER_BAYER4:
            dither_bayer4x4(scaled, dst, dst_w, dst_h);
            break;
        case DITHER_BAYER8:
            dither_bayer8x8(scaled, dst, dst_w, dst_h);
            break;
        case DITHER_FLOYD_STEINBERG:
            dither_floyd_steinberg(scaled, dst, dst_w, dst_h);
            break;
        case DITHER_THRESHOLD:
            dither_threshold(scaled, dst, dst_w, dst_h, 128);
            break;
    }

    heap_free(scaled);
}

/*
 * Draw dithered grayscale image to framebuffer
 */
void dither_draw_to_fb(const u8* gray_src, int src_w, int src_h,
                       int x, int y, dither_mode_t mode) {
    int dst_bytes = ((src_w + 7) / 8) * src_h;
    u8* dithered = (u8*)heap_alloc(dst_bytes);
    if (!dithered) return;

    switch (mode) {
        case DITHER_BAYER4:
            dither_bayer4x4(gray_src, dithered, src_w, src_h);
            break;
        case DITHER_BAYER8:
            dither_bayer8x8(gray_src, dithered, src_w, src_h);
            break;
        case DITHER_FLOYD_STEINBERG:
            dither_floyd_steinberg(gray_src, dithered, src_w, src_h);
            break;
        case DITHER_THRESHOLD:
            dither_threshold(gray_src, dithered, src_w, src_h, 128);
            break;
    }

    fb_draw_bitmap(x, y, dithered, src_w, src_h);
    heap_free(dithered);
}
