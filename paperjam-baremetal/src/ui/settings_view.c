/*
 * PaperJam Bare-Metal OS - Settings View
 *
 * User settings and configuration screen
 */

#include "hal/bcm2837.h"
#include "settings_view.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "gfx/icons.h"
#include "app/settings.h"
#include "app/player.h"
#include "drivers/audio.h"
#include "drivers/pisugar3.h"

/* Layout constants */
#define HEADER_HEIGHT   14
#define ITEM_HEIGHT     14
#define MARGIN          4
#define VALUE_X         120

/* Setting types */
typedef enum {
    SETTING_TOGGLE,
    SETTING_RANGE,
    SETTING_ACTION
} setting_type_t;

/* Setting item */
typedef struct {
    const char* label;
    setting_type_t type;
    int min_value;
    int max_value;
    int step;
    int (*get_value)(void);
    void (*set_value)(int);
    void (*action)(void);
} setting_item_t;

/* State */
static int view_active = 0;
static int selected_item = 0;
static int editing = 0;

/* Forward declarations for getters/setters */
static int get_shuffle(void) { return player_get_shuffle(); }
static void set_shuffle(int v) { player_set_shuffle(v); }

static int get_repeat(void) { return player_get_repeat(); }
static void set_repeat(int v) { player_set_repeat(v); }

static int get_volume(void) { return audio_get_volume(); }
static void set_volume(int v) { audio_set_volume(v); }

static int get_screensaver_timeout(void) { return settings_get_screensaver_timeout(); }
static void set_screensaver_timeout(int v) { settings_set_screensaver_timeout(v); }

/* Display sleep setting - stored in settings structure's reserved area */
static int display_sleep_enabled = 1;
static int get_display_sleep(void) { return display_sleep_enabled; }
static void set_display_sleep(int v) { display_sleep_enabled = v; }

static void action_rescan_library(void);
static void action_reset_settings(void);
static void action_system_info(void);

/* Settings items */
static const setting_item_t settings_items[] = {
    /* Playback section */
    { "Shuffle", SETTING_TOGGLE, 0, 1, 1, get_shuffle, set_shuffle, NULL },
    { "Repeat", SETTING_RANGE, 0, 2, 1, get_repeat, set_repeat, NULL },  /* 0=off, 1=all, 2=one */
    { "Volume", SETTING_RANGE, 0, 100, 5, get_volume, set_volume, NULL },

    /* Display section */
    { "Screensaver (sec)", SETTING_RANGE, 30, 300, 30, get_screensaver_timeout, set_screensaver_timeout, NULL },
    { "Display Sleep", SETTING_TOGGLE, 0, 1, 1, get_display_sleep, set_display_sleep, NULL },

    /* Actions section */
    { "Rescan Library", SETTING_ACTION, 0, 0, 0, NULL, NULL, action_rescan_library },
    { "Reset Settings", SETTING_ACTION, 0, 0, 0, NULL, NULL, action_reset_settings },
    { "System Info", SETTING_ACTION, 0, 0, 0, NULL, NULL, action_system_info },
};

#define SETTINGS_COUNT (sizeof(settings_items) / sizeof(settings_items[0]))

/* Action implementations */
static int showing_info = 0;

static void action_rescan_library(void) {
    /* TODO: Trigger library rescan */
}

static void action_reset_settings(void) {
    settings_reset();
    player_set_shuffle(0);
    player_set_repeat(0);
    audio_set_volume(50);
}

static void action_system_info(void) {
    showing_info = 1;
}

/*
 * Initialize settings view
 */
void settings_view_init(void) {
    view_active = 0;
    selected_item = 0;
    editing = 0;
    showing_info = 0;
}

/*
 * Enter settings view
 */
void settings_view_enter(void) {
    view_active = 1;
    selected_item = 0;
    editing = 0;
    showing_info = 0;
}

/*
 * Exit settings view
 */
void settings_view_exit(void) {
    /* Save settings on exit */
    settings_save();
    view_active = 0;
    showing_info = 0;
}

/*
 * Check if active
 */
int settings_view_is_active(void) {
    return view_active;
}

/*
 * Handle button press
 */
int settings_view_handle_button(int button) {
    if (!view_active) return 0;

    /* Handle system info screen */
    if (showing_info) {
        if (button == BUTTON_BACK || button == BUTTON_ENTER) {
            showing_info = 0;
            return 1;
        }
        return 1;
    }

    const setting_item_t* item = &settings_items[selected_item];

    switch (button) {
        case BUTTON_UP:
            if (!editing) {
                selected_item--;
                if (selected_item < 0) selected_item = SETTINGS_COUNT - 1;
            } else if (item->type == SETTING_RANGE && item->set_value) {
                int val = item->get_value();
                val += item->step;
                if (val > item->max_value) val = item->max_value;
                item->set_value(val);
            }
            return 1;

        case BUTTON_DOWN:
            if (!editing) {
                selected_item++;
                if (selected_item >= (int)SETTINGS_COUNT) selected_item = 0;
            } else if (item->type == SETTING_RANGE && item->set_value) {
                int val = item->get_value();
                val -= item->step;
                if (val < item->min_value) val = item->min_value;
                item->set_value(val);
            }
            return 1;

        case BUTTON_ENTER:
            if (item->type == SETTING_TOGGLE && item->set_value) {
                int val = item->get_value();
                item->set_value(val ? 0 : 1);
            } else if (item->type == SETTING_RANGE) {
                editing = !editing;
            } else if (item->type == SETTING_ACTION && item->action) {
                item->action();
            }
            return 1;

        case BUTTON_BACK:
            if (editing) {
                editing = 0;
            } else {
                settings_view_exit();
            }
            return 1;

        case BUTTON_VOL_UP:
            if (item->type == SETTING_RANGE && item->set_value) {
                int val = item->get_value();
                val += item->step;
                if (val > item->max_value) val = item->max_value;
                item->set_value(val);
            }
            return 1;

        case BUTTON_VOL_DOWN:
            if (item->type == SETTING_RANGE && item->set_value) {
                int val = item->get_value();
                val -= item->step;
                if (val < item->min_value) val = item->min_value;
                item->set_value(val);
            }
            return 1;
    }

    return 0;
}

/*
 * Draw value string
 */
static void draw_value(int x, int y, const setting_item_t* item, int highlight) {
    char buf[32];

    if (item->type == SETTING_TOGGLE && item->get_value) {
        int val = item->get_value();
        const char* str = val ? "On" : "Off";
        font_draw_string(x, y, str, highlight ? 0 : 1);
    }
    else if (item->type == SETTING_RANGE && item->get_value) {
        int val = item->get_value();

        /* Special handling for repeat mode */
        if (item->max_value == 2 && item->min_value == 0) {
            const char* modes[] = { "Off", "All", "One" };
            font_draw_string(x, y, modes[val], highlight ? 0 : 1);
        } else {
            /* Numeric value */
            int i = 0;
            if (val >= 100) buf[i++] = '0' + (val / 100);
            if (val >= 10) buf[i++] = '0' + ((val / 10) % 10);
            buf[i++] = '0' + (val % 10);
            buf[i] = '\0';
            font_draw_string(x, y, buf, highlight ? 0 : 1);
        }
    }
    else if (item->type == SETTING_ACTION) {
        font_draw_string(x, y, ">", highlight ? 0 : 1);
    }
}

/*
 * Draw system info screen
 */
static void draw_system_info(void) {
    fb_clear(1);

    /* Title */
    fb_fill_rect(0, 0, FB_WIDTH, HEADER_HEIGHT, 0);
    text_draw_aligned(0, 3, FB_WIDTH, "System Info", TEXT_ALIGN_CENTER, 0);

    int y = HEADER_HEIGHT + MARGIN;

    /* Battery */
    font_draw_string(MARGIN, y, "Battery:", 1);
    char buf[32];
    int bat = pisugar_get_cached_level();
    int i = 0;
    if (bat >= 100) buf[i++] = '1';
    buf[i++] = '0' + ((bat / 10) % 10);
    buf[i++] = '0' + (bat % 10);
    buf[i++] = '%';
    if (pisugar_is_charging()) {
        buf[i++] = ' ';
        buf[i++] = '(';
        buf[i++] = 'C';
        buf[i++] = 'h';
        buf[i++] = 'g';
        buf[i++] = ')';
    }
    buf[i] = '\0';
    font_draw_string(VALUE_X, y, buf, 1);
    y += ITEM_HEIGHT;

    /* Version */
    font_draw_string(MARGIN, y, "Version:", 1);
    font_draw_string(VALUE_X, y, "1.0.0", 1);
    y += ITEM_HEIGHT;

    /* Display */
    font_draw_string(MARGIN, y, "Display:", 1);
    font_draw_string(VALUE_X, y, "250x122 1-bit", 1);
    y += ITEM_HEIGHT;

    /* Platform */
    font_draw_string(MARGIN, y, "Platform:", 1);
    font_draw_string(VALUE_X, y, "RPi Zero 2 W", 1);
    y += ITEM_HEIGHT;

    /* Instructions */
    y = FB_HEIGHT - 12;
    text_draw_aligned(0, y, FB_WIDTH, "Press BACK to return", TEXT_ALIGN_CENTER, 1);
}

/*
 * Draw settings view
 */
void settings_view_draw(void) {
    if (!view_active) return;

    if (showing_info) {
        draw_system_info();
        return;
    }

    fb_clear(1);

    /* Header */
    fb_fill_rect(0, 0, FB_WIDTH, HEADER_HEIGHT, 0);
    icon_draw(MARGIN, (HEADER_HEIGHT - ICON_SIZE) / 2 + 1, ICON_SETTINGS, 0);
    text_draw_aligned(ICON_SIZE + MARGIN * 2, 3, FB_WIDTH - ICON_SIZE - MARGIN * 3,
                     "Settings", TEXT_ALIGN_LEFT, 0);

    /* Calculate visible items */
    int visible_items = (FB_HEIGHT - HEADER_HEIGHT - MARGIN) / ITEM_HEIGHT;
    int scroll_offset = 0;

    if (selected_item >= visible_items) {
        scroll_offset = selected_item - visible_items + 1;
    }

    /* Draw items */
    int y = HEADER_HEIGHT + MARGIN;

    for (int i = 0; i < visible_items && (i + scroll_offset) < (int)SETTINGS_COUNT; i++) {
        int idx = i + scroll_offset;
        const setting_item_t* item = &settings_items[idx];
        int selected = (idx == selected_item);
        int is_editing = (selected && editing);

        /* Selection highlight */
        if (selected) {
            fb_fill_rect(0, y, FB_WIDTH, ITEM_HEIGHT, 0);
        }

        /* Label */
        font_draw_string(MARGIN, y + 3, item->label, selected ? 0 : 1);

        /* Value */
        if (is_editing) {
            /* Draw value with edit indicators */
            fb_fill_rect(VALUE_X - 2, y + 1, FB_WIDTH - VALUE_X, ITEM_HEIGHT - 2, 1);
            draw_value(VALUE_X, y + 3, item, 0);

            /* Draw up/down arrows */
            font_draw_char(FB_WIDTH - 16, y + 3, '^', 1);
            font_draw_char(FB_WIDTH - 8, y + 3, 'v', 1);
        } else {
            draw_value(VALUE_X, y + 3, item, selected);
        }

        y += ITEM_HEIGHT;
    }

    /* Scroll indicator if needed */
    if (SETTINGS_COUNT > (u32)visible_items) {
        int scroll_h = (FB_HEIGHT - HEADER_HEIGHT) * visible_items / SETTINGS_COUNT;
        int scroll_y = HEADER_HEIGHT + (FB_HEIGHT - HEADER_HEIGHT - scroll_h) * scroll_offset / (SETTINGS_COUNT - visible_items);

        fb_fill_rect(FB_WIDTH - 3, scroll_y, 2, scroll_h, 0);
    }
}
