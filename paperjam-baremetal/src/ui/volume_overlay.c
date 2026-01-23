/*
 * PaperJam Bare-Metal OS - Volume Overlay
 *
 * Temporary overlay showing volume level
 */

#include "hal/bcm2837.h"
#include "hal/timer.h"
#include "volume_overlay.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "drivers/audio.h"

/* Overlay configuration */
#define OVERLAY_WIDTH       80
#define OVERLAY_HEIGHT      50
#define OVERLAY_MARGIN      10
#define OVERLAY_DURATION_MS 1500

/* Overlay state */
static int overlay_visible = 0;
static u64 overlay_show_time = 0;
static int overlay_volume = 0;
static u8* saved_region = NULL;
static int saved_x, saved_y;

/*
 * Initialize volume overlay
 */
void volume_overlay_init(void) {
    overlay_visible = 0;
    saved_region = NULL;
}

/*
 * Show volume overlay
 */
void volume_overlay_show(int volume) {
    /* Calculate position (bottom-center) */
    int x = (FB_WIDTH - OVERLAY_WIDTH) / 2;
    int y = FB_HEIGHT - OVERLAY_HEIGHT - OVERLAY_MARGIN;

    /* Save region if not already saved */
    if (!saved_region) {
        saved_region = (u8*)heap_alloc(OVERLAY_WIDTH * OVERLAY_HEIGHT / 8);
    }

    if (saved_region && !overlay_visible) {
        /* Save pixels under overlay */
        saved_x = x;
        saved_y = y;
        int bytes_per_row = (OVERLAY_WIDTH + 7) / 8;

        for (int row = 0; row < OVERLAY_HEIGHT; row++) {
            for (int col = 0; col < bytes_per_row; col++) {
                u8 byte = 0;
                for (int bit = 0; bit < 8; bit++) {
                    int px = col * 8 + bit;
                    if (px < OVERLAY_WIDTH) {
                        if (fb_get_pixel(x + px, y + row)) {
                            byte |= (0x80 >> bit);
                        }
                    }
                }
                saved_region[row * bytes_per_row + col] = byte;
            }
        }
    }

    overlay_volume = volume;
    overlay_visible = 1;
    overlay_show_time = timer_get_ms();

    /* Draw overlay */
    volume_overlay_draw();
}

/*
 * Hide volume overlay
 */
void volume_overlay_hide(void) {
    if (!overlay_visible) return;

    /* Restore saved region */
    if (saved_region) {
        int x = saved_x;
        int y = saved_y;
        int bytes_per_row = (OVERLAY_WIDTH + 7) / 8;

        for (int row = 0; row < OVERLAY_HEIGHT; row++) {
            for (int col = 0; col < bytes_per_row; col++) {
                u8 byte = saved_region[row * bytes_per_row + col];
                for (int bit = 0; bit < 8; bit++) {
                    int px = col * 8 + bit;
                    if (px < OVERLAY_WIDTH) {
                        int pixel = (byte >> (7 - bit)) & 1;
                        fb_set_pixel(x + px, y + row, pixel);
                    }
                }
            }
        }
    }

    overlay_visible = 0;
}

/*
 * Draw volume overlay
 */
void volume_overlay_draw(void) {
    if (!overlay_visible) return;

    int x = (FB_WIDTH - OVERLAY_WIDTH) / 2;
    int y = FB_HEIGHT - OVERLAY_HEIGHT - OVERLAY_MARGIN;

    /* Draw background */
    fb_fill_rect(x, y, OVERLAY_WIDTH, OVERLAY_HEIGHT, 1);
    fb_rect(x, y, OVERLAY_WIDTH, OVERLAY_HEIGHT, 0);
    fb_rect(x + 1, y + 1, OVERLAY_WIDTH - 2, OVERLAY_HEIGHT - 2, 0);

    /* Draw "Volume" label */
    text_draw_aligned(x, y + 5, OVERLAY_WIDTH, "Volume", TEXT_ALIGN_CENTER, 1);

    /* Draw volume percentage */
    char vol_str[8];
    int vi = 0;
    if (overlay_volume >= 100) vol_str[vi++] = '1';
    vol_str[vi++] = '0' + ((overlay_volume / 10) % 10);
    vol_str[vi++] = '0' + (overlay_volume % 10);
    vol_str[vi++] = '%';
    vol_str[vi] = '\0';

    text_draw_aligned(x, y + 18, OVERLAY_WIDTH, vol_str, TEXT_ALIGN_CENTER, 1);

    /* Draw volume bar */
    int bar_x = x + 8;
    int bar_y = y + 32;
    int bar_w = OVERLAY_WIDTH - 16;
    int bar_h = 10;

    fb_rect(bar_x, bar_y, bar_w, bar_h, 0);

    int fill_w = (bar_w - 2) * overlay_volume / 100;
    if (fill_w > 0) {
        fb_fill_rect(bar_x + 1, bar_y + 1, fill_w, bar_h - 2, 0);
    }

    /* Draw mute indicator if volume is 0 */
    if (overlay_volume == 0) {
        /* Draw X over speaker icon */
        fb_line(x + 5, y + 15, x + 15, y + 25, 0);
        fb_line(x + 15, y + 15, x + 5, y + 25, 0);
    }
}

/*
 * Update volume overlay (call from main loop)
 */
void volume_overlay_update(void) {
    if (!overlay_visible) return;

    /* Auto-hide after timeout */
    u64 now = timer_get_ms();
    if (now - overlay_show_time > OVERLAY_DURATION_MS) {
        volume_overlay_hide();
    }
}

/*
 * Check if overlay is visible
 */
int volume_overlay_is_visible(void) {
    return overlay_visible;
}

/*
 * Free overlay resources
 */
void volume_overlay_cleanup(void) {
    if (saved_region) {
        heap_free(saved_region);
        saved_region = NULL;
    }
    overlay_visible = 0;
}
