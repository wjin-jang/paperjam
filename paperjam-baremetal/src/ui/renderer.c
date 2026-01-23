/*
 * PaperJam Bare-Metal OS - Main UI Renderer
 */

#include "hal/bcm2837.h"
#include "hal/timer.h"
#include "renderer.h"
#include "menu.h"
#include "music_view.h"
#include "screensaver.h"
#include "browse_view.h"
#include "volume_overlay.h"
#include "context_menu.h"
#include "settings_view.h"
#include "gfx/framebuffer.h"
#include "drivers/epd_2in13_v4.h"
#include "drivers/buttons.h"
#include "sys/heap.h"

/* Renderer state */
static ui_view_t current_view = UI_VIEW_MUSIC;
static int needs_refresh = 1;
static int needs_full_refresh = 0;
static u64 last_render_time = 0;

/* Minimum time between renders (ms) */
#define MIN_RENDER_INTERVAL     100
#define FULL_REFRESH_INTERVAL   120

/*
 * Initialize renderer
 */
void renderer_init(void) {
    fb_init();
    menu_init();
    music_view_init();
    screensaver_init();

    current_view = UI_VIEW_MUSIC;
    needs_refresh = 1;
    needs_full_refresh = 1;
}

/*
 * Set current view
 */
void renderer_set_view(ui_view_t view) {
    if (current_view != view) {
        current_view = view;
        needs_refresh = 1;
    }
}

/*
 * Get current view
 */
ui_view_t renderer_get_view(void) {
    return current_view;
}

/*
 * Mark display as needing refresh
 */
void renderer_invalidate(void) {
    needs_refresh = 1;
}

/*
 * Request full refresh
 */
void renderer_request_full_refresh(void) {
    needs_full_refresh = 1;
    needs_refresh = 1;
}

/*
 * Draw current view to framebuffer
 */
static void render_view(void) {
    /* Settings view overlays everything except screensaver */
    if (settings_view_is_active()) {
        settings_view_draw();

        /* Draw context menu on top if visible */
        if (context_menu_is_visible()) {
            context_menu_draw();
        }

        /* Draw volume overlay on top */
        if (volume_overlay_is_visible()) {
            volume_overlay_draw();
        }
        return;
    }

    switch (current_view) {
        case UI_VIEW_MUSIC:
            music_view_draw();
            break;

        case UI_VIEW_MENU:
            menu_draw();
            break;

        case UI_VIEW_BROWSE:
            browse_view_draw();
            break;

        case UI_VIEW_SCREENSAVER:
            screensaver_draw();
            return;  /* Screensaver handles its own display */
    }

    /* Draw context menu on top if visible */
    if (context_menu_is_visible()) {
        context_menu_draw();
    }

    /* Draw volume overlay on top */
    if (volume_overlay_is_visible()) {
        volume_overlay_draw();
    }
}

/*
 * Render and update display
 */
void renderer_render(void) {
    /* Check if screensaver should activate */
    if (!screensaver_is_active() && screensaver_should_activate()) {
        current_view = UI_VIEW_SCREENSAVER;
        screensaver_activate();
        return;
    }

    /* Don't render if nothing changed */
    if (!needs_refresh) return;

    /* Rate limit rendering */
    u64 now = timer_get_ms();
    if (now - last_render_time < MIN_RENDER_INTERVAL) {
        return;
    }

    /* Render to framebuffer */
    render_view();

    /* Update e-paper display */
    if (needs_full_refresh || epd_get_partial_count() >= FULL_REFRESH_INTERVAL) {
        epd_display(fb_get_buffer());
        needs_full_refresh = 0;
    } else {
        epd_display_partial(fb_get_buffer());
    }

    needs_refresh = 0;
    last_render_time = now;
}

/*
 * Handle button input
 */
void renderer_handle_button(int button) {
    /* Wake from screensaver on any button */
    if (screensaver_is_active()) {
        screensaver_deactivate();
        current_view = UI_VIEW_MUSIC;
        needs_refresh = 1;
        return;
    }

    /* Reset screensaver timer */
    screensaver_reset();

    /* Context menu takes priority */
    if (context_menu_is_visible()) {
        if (context_menu_handle_button(button)) {
            needs_refresh = 1;
            return;
        }
    }

    /* Settings view takes priority */
    if (settings_view_is_active()) {
        if (settings_view_handle_button(button)) {
            needs_refresh = 1;
            return;
        }
    }

    /* Handle based on current view */
    switch (current_view) {
        case UI_VIEW_MUSIC:
            music_view_handle_button(button);
            break;

        case UI_VIEW_MENU:
            menu_handle_button(button);
            break;

        case UI_VIEW_BROWSE:
            browse_view_handle_button(button);
            break;

        default:
            break;
    }

    needs_refresh = 1;
}

/*
 * Handle long press
 */
void renderer_handle_long_press(int action) {
    screensaver_reset();

    switch (action) {
        case BUTTON_LONG_SHOW_QUEUE:
            music_view_set_mode(MUSIC_VIEW_QUEUE);
            current_view = UI_VIEW_MENU;
            break;

        case BUTTON_LONG_CONTEXT_MENU:
            current_view = UI_VIEW_MENU;
            break;

        case BUTTON_LONG_HOME:
            /* Close any open views and return to now playing */
            context_menu_hide();
            if (settings_view_is_active()) {
                settings_view_exit();
            }
            current_view = UI_VIEW_MUSIC;
            music_view_set_mode(MUSIC_VIEW_NOW_PLAYING);
            break;

        case BUTTON_LONG_SETTINGS:
            settings_view_enter();
            break;

        case BUTTON_LONG_BROWSE:
            browse_view_refresh();
            current_view = UI_VIEW_BROWSE;
            break;
    }

    needs_refresh = 1;
}

/*
 * Update (call from main loop)
 */
void renderer_update(void) {
    /* Update subsystems */
    music_view_update();
    screensaver_update();

    /* Update volume overlay (handles auto-hide) */
    int was_visible = volume_overlay_is_visible();
    volume_overlay_update();
    if (was_visible && !volume_overlay_is_visible()) {
        needs_refresh = 1;
    }

    /* Render if needed */
    renderer_render();
}

/*
 * Show popup message
 */
void renderer_show_popup(const char* message, int duration_ms) {
    /* Save current framebuffer */
    u8* saved = (u8*)heap_alloc(FB_SIZE);
    if (saved) {
        fb_copy_to(saved);
    }

    /* Draw popup */
    int popup_w = 100;
    int popup_h = 40;
    int popup_x = (FB_WIDTH - popup_w) / 2;
    int popup_y = (FB_HEIGHT - popup_h) / 2;

    fb_fill_rect(popup_x, popup_y, popup_w, popup_h, 1);
    fb_rect(popup_x, popup_y, popup_w, popup_h, 0);
    text_draw_aligned(popup_x, popup_y + popup_h / 2 - 4, popup_w,
                      message, TEXT_ALIGN_CENTER, 1);

    epd_display_partial(fb_get_buffer());

    /* Wait */
    timer_delay_ms(duration_ms);

    /* Restore */
    if (saved) {
        fb_copy_from(saved);
        epd_display_partial(fb_get_buffer());
        heap_free(saved);
    }
}

/*
 * Show volume popup
 */
void renderer_show_volume(int volume) {
    char buf[16];
    buf[0] = 'V';
    buf[1] = 'o';
    buf[2] = 'l';
    buf[3] = ':';
    buf[4] = ' ';
    int i = 5;
    if (volume >= 100) buf[i++] = '1';
    if (volume >= 10) buf[i++] = '0' + ((volume / 10) % 10);
    buf[i++] = '0' + (volume % 10);
    buf[i] = '\0';

    renderer_show_popup(buf, 500);
}
