/*
 * PaperJam Bare-Metal OS - 1-bit Framebuffer
 *
 * 250x122 pixels, 1-bit (16 bytes per row)
 * Pixel format: 1 = white, 0 = black (e-paper convention)
 */

#include "hal/bcm2837.h"
#include "framebuffer.h"
#include "sys/heap.h"

/* Display dimensions */
#define FB_WIDTH        122
#define FB_HEIGHT       250
#define FB_WIDTH_BYTES  ((FB_WIDTH + 7) / 8)
#define FB_SIZE         (FB_WIDTH_BYTES * FB_HEIGHT)

/* Framebuffer memory */
static u8 framebuffer[FB_SIZE];

/*
 * Initialize framebuffer (clear to white)
 */
void fb_init(void) {
    fb_clear(1);
}

/*
 * Clear framebuffer
 * color: 0 = black, 1 = white
 */
void fb_clear(int color) {
    memset(framebuffer, color ? 0xFF : 0x00, FB_SIZE);
}

/*
 * Get pixel value
 */
int fb_get_pixel(int x, int y) {
    if (x < 0 || x >= FB_WIDTH || y < 0 || y >= FB_HEIGHT) {
        return 1;  /* Out of bounds = white */
    }

    int byte_idx = y * FB_WIDTH_BYTES + (x / 8);
    int bit_idx = 7 - (x % 8);

    return (framebuffer[byte_idx] >> bit_idx) & 1;
}

/*
 * Set pixel value
 * color: 0 = black, 1 = white
 */
void fb_set_pixel(int x, int y, int color) {
    if (x < 0 || x >= FB_WIDTH || y < 0 || y >= FB_HEIGHT) {
        return;
    }

    int byte_idx = y * FB_WIDTH_BYTES + (x / 8);
    int bit_idx = 7 - (x % 8);

    if (color) {
        framebuffer[byte_idx] |= (1 << bit_idx);
    } else {
        framebuffer[byte_idx] &= ~(1 << bit_idx);
    }
}

/*
 * Toggle pixel
 */
void fb_toggle_pixel(int x, int y) {
    fb_set_pixel(x, y, !fb_get_pixel(x, y));
}

/*
 * Draw horizontal line
 */
void fb_hline(int x, int y, int w, int color) {
    for (int i = 0; i < w; i++) {
        fb_set_pixel(x + i, y, color);
    }
}

/*
 * Draw vertical line
 */
void fb_vline(int x, int y, int h, int color) {
    for (int i = 0; i < h; i++) {
        fb_set_pixel(x, y + i, color);
    }
}

/*
 * Draw line (Bresenham's algorithm)
 */
void fb_line(int x0, int y0, int x1, int y1, int color) {
    int dx = x1 - x0;
    int dy = y1 - y0;
    int sx = dx > 0 ? 1 : -1;
    int sy = dy > 0 ? 1 : -1;

    if (dx < 0) dx = -dx;
    if (dy < 0) dy = -dy;

    int err = (dx > dy ? dx : -dy) / 2;

    while (1) {
        fb_set_pixel(x0, y0, color);

        if (x0 == x1 && y0 == y1) break;

        int e2 = err;
        if (e2 > -dx) {
            err -= dy;
            x0 += sx;
        }
        if (e2 < dy) {
            err += dx;
            y0 += sy;
        }
    }
}

/*
 * Draw rectangle outline
 */
void fb_rect(int x, int y, int w, int h, int color) {
    fb_hline(x, y, w, color);
    fb_hline(x, y + h - 1, w, color);
    fb_vline(x, y, h, color);
    fb_vline(x + w - 1, y, h, color);
}

/*
 * Fill rectangle
 */
void fb_fill_rect(int x, int y, int w, int h, int color) {
    for (int j = 0; j < h; j++) {
        fb_hline(x, y + j, w, color);
    }
}

/*
 * Draw circle outline (midpoint algorithm)
 */
void fb_circle(int cx, int cy, int r, int color) {
    int x = r;
    int y = 0;
    int err = 0;

    while (x >= y) {
        fb_set_pixel(cx + x, cy + y, color);
        fb_set_pixel(cx + y, cy + x, color);
        fb_set_pixel(cx - y, cy + x, color);
        fb_set_pixel(cx - x, cy + y, color);
        fb_set_pixel(cx - x, cy - y, color);
        fb_set_pixel(cx - y, cy - x, color);
        fb_set_pixel(cx + y, cy - x, color);
        fb_set_pixel(cx + x, cy - y, color);

        if (err <= 0) {
            y++;
            err += 2 * y + 1;
        }
        if (err > 0) {
            x--;
            err -= 2 * x + 1;
        }
    }
}

/*
 * Fill circle
 */
void fb_fill_circle(int cx, int cy, int r, int color) {
    for (int y = -r; y <= r; y++) {
        for (int x = -r; x <= r; x++) {
            if (x * x + y * y <= r * r) {
                fb_set_pixel(cx + x, cy + y, color);
            }
        }
    }
}

/*
 * Draw 1-bit bitmap
 */
void fb_draw_bitmap(int x, int y, const u8* bitmap, int w, int h) {
    int bytes_per_row = (w + 7) / 8;

    for (int j = 0; j < h; j++) {
        for (int i = 0; i < w; i++) {
            int byte_idx = j * bytes_per_row + (i / 8);
            int bit_idx = 7 - (i % 8);
            int pixel = (bitmap[byte_idx] >> bit_idx) & 1;
            fb_set_pixel(x + i, y + j, pixel);
        }
    }
}

/*
 * Draw 1-bit bitmap with transparency (white = transparent)
 */
void fb_draw_bitmap_transparent(int x, int y, const u8* bitmap, int w, int h) {
    int bytes_per_row = (w + 7) / 8;

    for (int j = 0; j < h; j++) {
        for (int i = 0; i < w; i++) {
            int byte_idx = j * bytes_per_row + (i / 8);
            int bit_idx = 7 - (i % 8);
            int pixel = (bitmap[byte_idx] >> bit_idx) & 1;
            if (!pixel) {  /* Only draw black pixels */
                fb_set_pixel(x + i, y + j, 0);
            }
        }
    }
}

/*
 * Invert a region
 */
void fb_invert_rect(int x, int y, int w, int h) {
    for (int j = 0; j < h; j++) {
        for (int i = 0; i < w; i++) {
            fb_toggle_pixel(x + i, y + j);
        }
    }
}

/*
 * Copy region
 */
void fb_copy_rect(int dst_x, int dst_y, int src_x, int src_y, int w, int h) {
    /* Use temporary buffer to handle overlapping regions */
    for (int j = 0; j < h; j++) {
        for (int i = 0; i < w; i++) {
            int pixel = fb_get_pixel(src_x + i, src_y + j);
            fb_set_pixel(dst_x + i, dst_y + j, pixel);
        }
    }
}

/*
 * Scroll region up
 */
void fb_scroll_up(int y, int h, int lines) {
    for (int j = 0; j < h - lines; j++) {
        for (int i = 0; i < FB_WIDTH_BYTES; i++) {
            framebuffer[(y + j) * FB_WIDTH_BYTES + i] =
                framebuffer[(y + j + lines) * FB_WIDTH_BYTES + i];
        }
    }
    /* Clear bottom */
    for (int j = h - lines; j < h; j++) {
        memset(&framebuffer[(y + j) * FB_WIDTH_BYTES], 0xFF, FB_WIDTH_BYTES);
    }
}

/*
 * Get pointer to framebuffer
 */
u8* fb_get_buffer(void) {
    return framebuffer;
}

/*
 * Get framebuffer dimensions
 */
int fb_get_width(void) {
    return FB_WIDTH;
}

int fb_get_height(void) {
    return FB_HEIGHT;
}

int fb_get_size(void) {
    return FB_SIZE;
}

/*
 * Copy external buffer to framebuffer
 */
void fb_copy_from(const u8* src) {
    memcpy(framebuffer, src, FB_SIZE);
}

/*
 * Copy framebuffer to external buffer
 */
void fb_copy_to(u8* dst) {
    memcpy(dst, framebuffer, FB_SIZE);
}
