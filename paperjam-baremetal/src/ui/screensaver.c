/*
 * PaperJam Bare-Metal OS - Screensaver
 */

#include "hal/bcm2837.h"
#include "hal/timer.h"
#include "screensaver.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "drivers/epd_2in13_v4.h"
#include "drivers/pisugar3.h"
#include "audio/playback.h"

/* Screensaver settings */
#define SCREENSAVER_TIMEOUT_MS  60000   /* 1 minute of inactivity */
#define CLOCK_UPDATE_MS         60000   /* Update clock every minute */

/* State */
static int screensaver_active = 0;
static u64 last_activity = 0;
static u64 last_clock_update = 0;
static int display_sleeping = 0;

/*
 * Initialize screensaver
 */
void screensaver_init(void) {
    screensaver_active = 0;
    last_activity = timer_get_ms();
    display_sleeping = 0;
}

/*
 * Reset activity timer
 */
void screensaver_reset(void) {
    last_activity = timer_get_ms();

    if (screensaver_active) {
        screensaver_deactivate();
    }
}

/*
 * Check if screensaver should activate
 */
int screensaver_should_activate(void) {
    if (screensaver_active) return 0;

    u64 now = timer_get_ms();
    return (now - last_activity) > SCREENSAVER_TIMEOUT_MS;
}

/*
 * Activate screensaver
 */
void screensaver_activate(void) {
    if (screensaver_active) return;

    screensaver_active = 1;
    last_clock_update = 0;  /* Force immediate update */

    /* Draw screensaver */
    screensaver_draw();

    /* Put display to sleep after drawing */
    epd_sleep();
    display_sleeping = 1;
}

/*
 * Deactivate screensaver
 */
void screensaver_deactivate(void) {
    if (!screensaver_active) return;

    if (display_sleeping) {
        epd_wake();
        display_sleeping = 0;
    }

    screensaver_active = 0;
    last_activity = timer_get_ms();
}

/*
 * Check if screensaver is active
 */
int screensaver_is_active(void) {
    return screensaver_active;
}

/*
 * Draw screensaver
 */
void screensaver_draw(void) {
    fb_clear(1);  /* White background */

    /* Center of screen */
    int center_x = FB_WIDTH / 2;
    int center_y = FB_HEIGHT / 2;

    /* Draw battery status */
    int battery = pisugar_get_cached_level();
    char bat_str[16];
    int i = 0;
    if (battery >= 100) bat_str[i++] = '1';
    bat_str[i++] = '0' + ((battery / 10) % 10);
    bat_str[i++] = '0' + (battery % 10);
    bat_str[i++] = '%';
    bat_str[i] = '\0';

    text_draw_aligned(0, center_y - 20, FB_WIDTH, bat_str, TEXT_ALIGN_CENTER, 1);

    /* Draw "PaperJam" */
    text_draw_aligned(0, center_y, FB_WIDTH, "PaperJam", TEXT_ALIGN_CENTER, 1);

    /* Draw playback status if playing */
    if (playback_is_playing()) {
        text_draw_aligned(0, center_y + 20, FB_WIDTH, "Playing...", TEXT_ALIGN_CENTER, 1);
    }

    /* Update display */
    if (!display_sleeping) {
        epd_display_partial(fb_get_buffer());
    }
}

/*
 * Update screensaver (call periodically)
 */
void screensaver_update(void) {
    if (!screensaver_active) {
        /* Check if we should activate */
        if (screensaver_should_activate()) {
            screensaver_activate();
        }
        return;
    }

    /* Periodic clock update */
    u64 now = timer_get_ms();
    if (now - last_clock_update > CLOCK_UPDATE_MS) {
        last_clock_update = now;

        /* Wake display briefly to update */
        if (display_sleeping) {
            epd_wake();
            display_sleeping = 0;
        }

        screensaver_draw();

        /* Sleep again */
        epd_sleep();
        display_sleeping = 1;
    }
}

/*
 * Set screensaver timeout
 */
static u32 screensaver_timeout = SCREENSAVER_TIMEOUT_MS;

void screensaver_set_timeout(u32 timeout_ms) {
    screensaver_timeout = timeout_ms;
}

u32 screensaver_get_timeout(void) {
    return screensaver_timeout;
}
