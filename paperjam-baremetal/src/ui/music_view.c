/*
 * PaperJam Bare-Metal OS - Music Player View
 */

#include "hal/bcm2837.h"
#include "hal/timer.h"
#include "music_view.h"
#include "volume_overlay.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "gfx/icons.h"
#include "audio/playback.h"
#include "drivers/pisugar3.h"
#include "drivers/audio.h"
#include "sys/heap.h"

/* Layout constants */
#define HEADER_HEIGHT       12
#define FOOTER_HEIGHT       20
#define PROGRESS_HEIGHT     8
#define MARGIN              4

/* View state */
static music_view_mode_t view_mode = MUSIC_VIEW_NOW_PLAYING;
static audio_metadata_t current_meta;
static int title_scroll = 0;
static u64 last_scroll_time = 0;

/*
 * Initialize music view
 */
void music_view_init(void) {
    view_mode = MUSIC_VIEW_NOW_PLAYING;
    memset(&current_meta, 0, sizeof(current_meta));
    title_scroll = 0;
}

/*
 * Set view mode
 */
void music_view_set_mode(music_view_mode_t mode) {
    view_mode = mode;
}

/*
 * Get view mode
 */
music_view_mode_t music_view_get_mode(void) {
    return view_mode;
}

/*
 * Update metadata from playback
 */
void music_view_update_metadata(void) {
    playback_get_metadata(&current_meta);
}

/*
 * Draw header with battery
 */
static void draw_header(void) {
    /* Draw separator line */
    fb_hline(0, HEADER_HEIGHT, FB_WIDTH, 0);

    /* Draw battery info */
    int battery = pisugar_get_cached_level();
    char icon = pisugar_get_battery_icon();

    char bat_str[8];
    int i = 0;
    bat_str[i++] = icon;
    bat_str[i++] = ' ';
    if (battery >= 100) bat_str[i++] = '1';
    if (battery >= 10) bat_str[i++] = '0' + ((battery / 10) % 10);
    bat_str[i++] = '0' + (battery % 10);
    bat_str[i++] = '%';
    bat_str[i] = '\0';

    /* Right-align battery */
    int bat_width = font_string_width(bat_str);
    font_draw_string(FB_WIDTH - bat_width - MARGIN, 2, bat_str, 1);

    /* Draw title based on mode */
    const char* title;
    switch (view_mode) {
        case MUSIC_VIEW_NOW_PLAYING:
            title = "Now Playing";
            break;
        case MUSIC_VIEW_BROWSE:
            title = "Browse";
            break;
        case MUSIC_VIEW_QUEUE:
            title = "Queue";
            break;
        default:
            title = "Music";
    }
    font_draw_string(MARGIN, 2, title, 1);
}

/*
 * Draw footer with playback info
 */
static void draw_footer(void) {
    int footer_y = FB_HEIGHT - FOOTER_HEIGHT;

    /* Draw separator */
    fb_hline(0, footer_y, FB_WIDTH, 0);

    /* Time display */
    u32 pos = playback_get_position();
    u32 dur = playback_get_duration();

    char time_str[16];
    playback_format_time(pos, time_str, sizeof(time_str));
    font_draw_string(MARGIN, footer_y + 4, time_str, 1);

    playback_format_time(dur, time_str, sizeof(time_str));
    int dur_width = font_string_width(time_str);
    font_draw_string(FB_WIDTH - dur_width - MARGIN, footer_y + 4, time_str, 1);

    /* Progress bar */
    int prog_y = footer_y + 14;
    int prog_w = FB_WIDTH - MARGIN * 2;
    int progress = playback_get_progress();
    text_draw_progress_bar(MARGIN, prog_y, prog_w, 4, progress, 1);
}

/*
 * Draw now playing view
 */
static void draw_now_playing(void) {
    draw_header();

    int content_y = HEADER_HEIGHT + MARGIN;
    int content_h = FB_HEIGHT - HEADER_HEIGHT - FOOTER_HEIGHT - MARGIN * 2;
    int center_y = content_y + content_h / 2;

    /* Play/pause icon */
    icon_id_t state_icon;
    if (playback_is_playing()) {
        state_icon = ICON_PLAY;
    } else if (playback_get_state() == PLAYBACK_PAUSED) {
        state_icon = ICON_PAUSE;
    } else {
        state_icon = ICON_STOP;
    }

    icon_draw_centered(0, center_y - 48, FB_WIDTH, 20, state_icon, 1);

    /* Title (scrolling if too long) */
    const char* title = current_meta.title[0] ? current_meta.title : "Unknown Title";
    text_draw_ellipsis(MARGIN, center_y - 20, FB_WIDTH - MARGIN * 2, title, 1);

    /* Artist */
    const char* artist = current_meta.artist[0] ? current_meta.artist : "Unknown Artist";
    text_draw_ellipsis(MARGIN, center_y - 8, FB_WIDTH - MARGIN * 2, artist, 1);

    /* Album */
    const char* album = current_meta.album[0] ? current_meta.album : "";
    if (album[0]) {
        text_draw_ellipsis(MARGIN, center_y + 4, FB_WIDTH - MARGIN * 2, album, 1);
    }

    /* Volume */
    int volume = audio_get_volume();
    char vol_str[16];
    vol_str[0] = 'V';
    vol_str[1] = 'o';
    vol_str[2] = 'l';
    vol_str[3] = ':';
    vol_str[4] = ' ';
    int vi = 5;
    if (volume >= 100) vol_str[vi++] = '1';
    if (volume >= 10) vol_str[vi++] = '0' + ((volume / 10) % 10);
    vol_str[vi++] = '0' + (volume % 10);
    vol_str[vi] = '\0';

    text_draw_aligned(0, center_y + 20, FB_WIDTH, vol_str, TEXT_ALIGN_CENTER, 1);

    draw_footer();
}

/*
 * Draw main view
 */
void music_view_draw(void) {
    fb_clear(1);

    switch (view_mode) {
        case MUSIC_VIEW_NOW_PLAYING:
            draw_now_playing();
            break;

        case MUSIC_VIEW_BROWSE:
        case MUSIC_VIEW_QUEUE:
            /* These would use the menu system */
            draw_header();
            font_draw_string(MARGIN, FB_HEIGHT / 2, "Use Menu", 1);
            break;
    }
}

/*
 * Handle button press
 */
void music_view_handle_button(int button) {
    switch (button) {
        case BUTTON_PLAY_PAUSE:
            playback_toggle();
            break;

        case BUTTON_PREV:
            playback_seek_relative(-10);
            break;

        case BUTTON_NEXT:
            playback_seek_relative(10);
            break;

        case BUTTON_VOL_UP:
            audio_adjust_volume(5);
            volume_overlay_show(audio_get_volume());
            break;

        case BUTTON_VOL_DOWN:
            audio_adjust_volume(-5);
            volume_overlay_show(audio_get_volume());
            break;

        case BUTTON_UP:
            /* Could cycle through views or other action */
            break;

        case BUTTON_DOWN:
            /* Could cycle through views or other action */
            break;
    }

    music_view_update_metadata();
}

/*
 * Update (call periodically)
 */
void music_view_update(void) {
    /* Update scrolling title */
    u64 now = timer_get_ms();
    if (now - last_scroll_time > 200) {
        title_scroll += 8;
        last_scroll_time = now;
    }
}
