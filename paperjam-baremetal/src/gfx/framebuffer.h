/*
 * PaperJam Bare-Metal OS - Framebuffer Header
 */

#ifndef FRAMEBUFFER_H
#define FRAMEBUFFER_H

#include "hal/bcm2837.h"

/* Display dimensions */
#define FB_WIDTH        122
#define FB_HEIGHT       250
#define FB_WIDTH_BYTES  ((FB_WIDTH + 7) / 8)
#define FB_SIZE         (FB_WIDTH_BYTES * FB_HEIGHT)

/* Function prototypes */
void fb_init(void);
void fb_clear(int color);
int  fb_get_pixel(int x, int y);
void fb_set_pixel(int x, int y, int color);
void fb_toggle_pixel(int x, int y);
void fb_hline(int x, int y, int w, int color);
void fb_vline(int x, int y, int h, int color);
void fb_line(int x0, int y0, int x1, int y1, int color);
void fb_rect(int x, int y, int w, int h, int color);
void fb_fill_rect(int x, int y, int w, int h, int color);
void fb_circle(int cx, int cy, int r, int color);
void fb_fill_circle(int cx, int cy, int r, int color);
void fb_draw_bitmap(int x, int y, const u8* bitmap, int w, int h);
void fb_draw_bitmap_transparent(int x, int y, const u8* bitmap, int w, int h);
void fb_invert_rect(int x, int y, int w, int h);
void fb_copy_rect(int dst_x, int dst_y, int src_x, int src_y, int w, int h);
void fb_scroll_up(int y, int h, int lines);
u8*  fb_get_buffer(void);
int  fb_get_width(void);
int  fb_get_height(void);
int  fb_get_size(void);
void fb_copy_from(const u8* src);
void fb_copy_to(u8* dst);

#endif /* FRAMEBUFFER_H */
