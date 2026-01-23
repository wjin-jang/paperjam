/*
 * PaperJam Bare-Metal OS - Context Menu
 *
 * Popup context menus for track/album options
 */

#include "hal/bcm2837.h"
#include "context_menu.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "app/favorites.h"
#include "app/playlist.h"
#include "app/player.h"
#include "drivers/buttons.h"
#include "sys/heap.h"

/* Layout constants */
#define MENU_PADDING        4
#define MENU_ITEM_HEIGHT    12
#define MENU_MIN_WIDTH      80
#define MENU_MAX_WIDTH      180
#define SEPARATOR_HEIGHT    6

/* State */
static context_menu_t* active_menu = NULL;
static u8* saved_region = NULL;
static int saved_x, saved_y, saved_w, saved_h;

/* Track context menu data */
static char context_track_path[256];

/*
 * Initialize context menu system
 */
void context_menu_init(void) {
    active_menu = NULL;
    saved_region = NULL;
}

/*
 * Create a new context menu
 */
context_menu_t* context_menu_create(const char* title) {
    context_menu_t* menu = (context_menu_t*)heap_alloc(sizeof(context_menu_t));
    if (!menu) return NULL;

    memset(menu, 0, sizeof(context_menu_t));
    menu->title = title;
    menu->x = -1;
    menu->y = -1;
    menu->width = 0;

    return menu;
}

/*
 * Add item to context menu
 */
int context_menu_add_item(context_menu_t* menu, const char* label,
                          void (*action)(void* data), void* data) {
    if (!menu || menu->item_count >= CONTEXT_MENU_MAX_ITEMS) return -1;

    int index = menu->item_count;
    menu->items[index].label = label;
    menu->items[index].action = action;
    menu->items[index].data = data;
    menu->items[index].enabled = 1;
    menu->item_count++;

    return index;
}

/*
 * Add separator
 */
void context_menu_add_separator(context_menu_t* menu) {
    if (!menu || menu->item_count >= CONTEXT_MENU_MAX_ITEMS) return;

    menu->items[menu->item_count].label = NULL;  /* NULL label = separator */
    menu->items[menu->item_count].action = NULL;
    menu->items[menu->item_count].enabled = 0;
    menu->item_count++;
}

/*
 * Enable/disable an item
 */
void context_menu_set_enabled(context_menu_t* menu, int index, int enabled) {
    if (!menu || index < 0 || index >= menu->item_count) return;
    menu->items[index].enabled = enabled;
}

/*
 * Calculate menu dimensions
 */
static void calculate_dimensions(context_menu_t* menu, int* out_w, int* out_h) {
    int max_width = MENU_MIN_WIDTH;
    int height = MENU_PADDING * 2;

    /* Title */
    if (menu->title) {
        int tw = font_string_width(menu->title);
        if (tw + MENU_PADDING * 2 > max_width) {
            max_width = tw + MENU_PADDING * 2;
        }
        height += MENU_ITEM_HEIGHT;
    }

    /* Items */
    for (int i = 0; i < menu->item_count; i++) {
        if (menu->items[i].label == NULL) {
            height += SEPARATOR_HEIGHT;
        } else {
            int iw = font_string_width(menu->items[i].label);
            if (iw + MENU_PADDING * 2 > max_width) {
                max_width = iw + MENU_PADDING * 2;
            }
            height += MENU_ITEM_HEIGHT;
        }
    }

    if (max_width > MENU_MAX_WIDTH) max_width = MENU_MAX_WIDTH;

    *out_w = max_width;
    *out_h = height;
}

/*
 * Save screen region under menu
 */
static void save_region(int x, int y, int w, int h) {
    int bytes_per_row = (w + 7) / 8;
    int size = bytes_per_row * h;

    if (saved_region) heap_free(saved_region);
    saved_region = (u8*)heap_alloc(size);

    if (saved_region) {
        saved_x = x;
        saved_y = y;
        saved_w = w;
        saved_h = h;

        for (int row = 0; row < h; row++) {
            for (int col = 0; col < bytes_per_row; col++) {
                u8 byte = 0;
                for (int bit = 0; bit < 8; bit++) {
                    int px = col * 8 + bit;
                    if (px < w) {
                        if (fb_get_pixel(x + px, y + row)) {
                            byte |= (0x80 >> bit);
                        }
                    }
                }
                saved_region[row * bytes_per_row + col] = byte;
            }
        }
    }
}

/*
 * Restore saved region
 */
static void restore_region(void) {
    if (!saved_region) return;

    int bytes_per_row = (saved_w + 7) / 8;

    for (int row = 0; row < saved_h; row++) {
        for (int col = 0; col < bytes_per_row; col++) {
            u8 byte = saved_region[row * bytes_per_row + col];
            for (int bit = 0; bit < 8; bit++) {
                int px = col * 8 + bit;
                if (px < saved_w) {
                    int pixel = (byte >> (7 - bit)) & 1;
                    fb_set_pixel(saved_x + px, saved_y + row, pixel);
                }
            }
        }
    }

    heap_free(saved_region);
    saved_region = NULL;
}

/*
 * Show context menu
 */
void context_menu_show(context_menu_t* menu, int x, int y) {
    if (!menu || menu->item_count == 0) return;

    /* Hide any existing menu */
    if (active_menu) {
        context_menu_hide();
    }

    /* Calculate dimensions */
    int w, h;
    calculate_dimensions(menu, &w, &h);

    /* Calculate position if not specified */
    if (x < 0) x = (FB_WIDTH - w) / 2;
    if (y < 0) y = (FB_HEIGHT - h) / 2;

    /* Clamp to screen */
    if (x + w > FB_WIDTH) x = FB_WIDTH - w;
    if (y + h > FB_HEIGHT) y = FB_HEIGHT - h;
    if (x < 0) x = 0;
    if (y < 0) y = 0;

    menu->x = x;
    menu->y = y;
    menu->width = w;
    menu->selected = 0;
    menu->visible = 1;

    /* Find first selectable item */
    while (menu->selected < menu->item_count &&
           (menu->items[menu->selected].label == NULL ||
            !menu->items[menu->selected].enabled)) {
        menu->selected++;
    }

    /* Save screen region */
    save_region(x, y, w, h);

    active_menu = menu;

    /* Draw menu */
    context_menu_draw();
}

/*
 * Hide context menu
 */
void context_menu_hide(void) {
    if (!active_menu) return;

    restore_region();
    active_menu->visible = 0;
    active_menu = NULL;
}

/*
 * Check if visible
 */
int context_menu_is_visible(void) {
    return active_menu != NULL;
}

/*
 * Handle button press
 */
int context_menu_handle_button(int button) {
    if (!active_menu) return 0;

    switch (button) {
        case BUTTON_UP:
            /* Move selection up */
            do {
                active_menu->selected--;
                if (active_menu->selected < 0) {
                    active_menu->selected = active_menu->item_count - 1;
                }
            } while (active_menu->items[active_menu->selected].label == NULL ||
                     !active_menu->items[active_menu->selected].enabled);
            context_menu_draw();
            return 1;

        case BUTTON_DOWN:
            /* Move selection down */
            do {
                active_menu->selected++;
                if (active_menu->selected >= active_menu->item_count) {
                    active_menu->selected = 0;
                }
            } while (active_menu->items[active_menu->selected].label == NULL ||
                     !active_menu->items[active_menu->selected].enabled);
            context_menu_draw();
            return 1;

        case BUTTON_ENTER:
            /* Execute selected action */
            if (active_menu->selected >= 0 &&
                active_menu->selected < active_menu->item_count) {
                context_menu_item_t* item = &active_menu->items[active_menu->selected];
                if (item->action && item->enabled) {
                    void (*action)(void*) = item->action;
                    void* data = item->data;
                    context_menu_hide();
                    action(data);
                }
            }
            return 1;

        case BUTTON_BACK:
            context_menu_hide();
            return 1;
    }

    return 0;
}

/*
 * Draw context menu
 */
void context_menu_draw(void) {
    if (!active_menu || !active_menu->visible) return;

    int x = active_menu->x;
    int y = active_menu->y;
    int w = active_menu->width;

    /* Calculate height */
    int h = MENU_PADDING * 2;
    if (active_menu->title) h += MENU_ITEM_HEIGHT;
    for (int i = 0; i < active_menu->item_count; i++) {
        h += (active_menu->items[i].label == NULL) ? SEPARATOR_HEIGHT : MENU_ITEM_HEIGHT;
    }

    /* Draw background */
    fb_fill_rect(x, y, w, h, 1);

    /* Draw border */
    fb_rect(x, y, w, h, 0);
    fb_rect(x + 1, y + 1, w - 2, h - 2, 0);

    int cy = y + MENU_PADDING;

    /* Draw title */
    if (active_menu->title) {
        text_draw_aligned(x + MENU_PADDING, cy, w - MENU_PADDING * 2,
                         active_menu->title, TEXT_ALIGN_CENTER, 1);
        cy += MENU_ITEM_HEIGHT;

        /* Separator line after title */
        fb_hline(x + 2, cy - 2, w - 4, 0);
    }

    /* Draw items */
    for (int i = 0; i < active_menu->item_count; i++) {
        if (active_menu->items[i].label == NULL) {
            /* Separator */
            fb_hline(x + MENU_PADDING, cy + SEPARATOR_HEIGHT / 2, w - MENU_PADDING * 2, 0);
            cy += SEPARATOR_HEIGHT;
        } else {
            /* Menu item */
            int selected = (i == active_menu->selected);
            int enabled = active_menu->items[i].enabled;

            if (selected) {
                /* Highlight selection */
                fb_fill_rect(x + 2, cy, w - 4, MENU_ITEM_HEIGHT, 0);
            }

            /* Draw label */
            if (enabled) {
                font_draw_string(x + MENU_PADDING, cy + 2,
                               active_menu->items[i].label, selected ? 0 : 1);
            } else {
                /* Disabled - draw with stipple pattern */
                const char* label = active_menu->items[i].label;
                int lx = x + MENU_PADDING;
                for (int c = 0; label[c]; c++) {
                    if ((lx + c * 8) & 1) {
                        font_draw_char(lx + c * 8, cy + 2, label[c], 1);
                    }
                }
            }

            cy += MENU_ITEM_HEIGHT;
        }
    }
}

/*
 * Destroy context menu
 */
void context_menu_destroy(context_menu_t* menu) {
    if (!menu) return;

    if (menu == active_menu) {
        context_menu_hide();
    }

    heap_free(menu);
}

/*
 * Get active menu
 */
context_menu_t* context_menu_get_active(void) {
    return active_menu;
}

/* Action callbacks for track menu */

static void action_play_now(void* data) {
    (void)data;
    player_play_file(context_track_path);
}

static void action_play_next(void* data) {
    (void)data;
    queue_add_next(context_track_path);
}

static void action_add_to_queue(void* data) {
    (void)data;
    queue_add(context_track_path);
}

static void action_toggle_favorite(void* data) {
    (void)data;
    favorites_toggle(context_track_path);
}

/*
 * Create track context menu
 */
context_menu_t* context_menu_create_track(const char* path) {
    context_menu_t* menu = context_menu_create("Track");
    if (!menu) return NULL;

    /* Save path for callbacks */
    strncpy(context_track_path, path, sizeof(context_track_path) - 1);
    context_track_path[sizeof(context_track_path) - 1] = '\0';

    context_menu_add_item(menu, "Play Now", action_play_now, NULL);
    context_menu_add_item(menu, "Play Next", action_play_next, NULL);
    context_menu_add_item(menu, "Add to Queue", action_add_to_queue, NULL);
    context_menu_add_separator(menu);

    if (favorites_is_favorite(path)) {
        context_menu_add_item(menu, "Remove from Favorites", action_toggle_favorite, NULL);
    } else {
        context_menu_add_item(menu, "Add to Favorites", action_toggle_favorite, NULL);
    }

    return menu;
}

/* Queue item action callbacks */
static int context_queue_index;

static void action_remove_from_queue(void* data) {
    (void)data;
    queue_remove(context_queue_index);
}

static void action_move_up(void* data) {
    (void)data;
    if (context_queue_index > 0) {
        queue_move(context_queue_index, context_queue_index - 1);
    }
}

static void action_move_down(void* data) {
    (void)data;
    if (context_queue_index < queue_count() - 1) {
        queue_move(context_queue_index, context_queue_index + 1);
    }
}

/*
 * Create queue item context menu
 */
context_menu_t* context_menu_create_queue_item(int queue_index) {
    context_menu_t* menu = context_menu_create("Queue Item");
    if (!menu) return NULL;

    context_queue_index = queue_index;

    const char* path = queue_get(queue_index);
    if (path) {
        strncpy(context_track_path, path, sizeof(context_track_path) - 1);
        context_track_path[sizeof(context_track_path) - 1] = '\0';
    }

    context_menu_add_item(menu, "Play Now", action_play_now, NULL);
    context_menu_add_item(menu, "Move Up", action_move_up, NULL);
    context_menu_add_item(menu, "Move Down", action_move_down, NULL);
    context_menu_add_separator(menu);
    context_menu_add_item(menu, "Remove", action_remove_from_queue, NULL);

    if (path && favorites_is_favorite(path)) {
        context_menu_add_item(menu, "Remove from Favorites", action_toggle_favorite, NULL);
    } else if (path) {
        context_menu_add_item(menu, "Add to Favorites", action_toggle_favorite, NULL);
    }

    return menu;
}
