/*
 * PaperJam Bare-Metal OS - Menu System
 */

#include "hal/bcm2837.h"
#include "menu.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "drivers/buttons.h"
#include "sys/heap.h"

/* Menu configuration */
#define MENU_ITEM_HEIGHT    12
#define MENU_PADDING        2
#define MENU_MARGIN         4

/* Current menu state */
static menu_t* current_menu = NULL;
static int selected_index = 0;
static int scroll_offset = 0;
static int visible_items = 0;

/*
 * Initialize menu system
 */
void menu_init(void) {
    current_menu = NULL;
    selected_index = 0;
    scroll_offset = 0;
}

/*
 * Set current menu
 */
void menu_set(menu_t* menu) {
    current_menu = menu;
    selected_index = 0;
    scroll_offset = 0;

    if (menu) {
        visible_items = (FB_HEIGHT - MENU_MARGIN * 2) / MENU_ITEM_HEIGHT;
    }
}

/*
 * Get current menu
 */
menu_t* menu_get(void) {
    return current_menu;
}

/*
 * Get selected index
 */
int menu_get_selected(void) {
    return selected_index;
}

/*
 * Set selected index
 */
void menu_set_selected(int index) {
    if (!current_menu) return;

    if (index < 0) index = 0;
    if (index >= current_menu->item_count) {
        index = current_menu->item_count - 1;
    }

    selected_index = index;

    /* Adjust scroll to keep selection visible */
    if (selected_index < scroll_offset) {
        scroll_offset = selected_index;
    }
    if (selected_index >= scroll_offset + visible_items) {
        scroll_offset = selected_index - visible_items + 1;
    }
}

/*
 * Move selection up
 */
void menu_up(void) {
    if (!current_menu || current_menu->item_count == 0) return;

    if (selected_index > 0) {
        selected_index--;
    } else if (current_menu->wrap) {
        selected_index = current_menu->item_count - 1;
    }

    /* Adjust scroll */
    if (selected_index < scroll_offset) {
        scroll_offset = selected_index;
    }
}

/*
 * Move selection down
 */
void menu_down(void) {
    if (!current_menu || current_menu->item_count == 0) return;

    if (selected_index < current_menu->item_count - 1) {
        selected_index++;
    } else if (current_menu->wrap) {
        selected_index = 0;
    }

    /* Adjust scroll */
    if (selected_index >= scroll_offset + visible_items) {
        scroll_offset = selected_index - visible_items + 1;
    }
}

/*
 * Select current item (enter)
 */
void menu_enter(void) {
    if (!current_menu || current_menu->item_count == 0) return;

    menu_item_t* item = &current_menu->items[selected_index];

    if (item->callback) {
        item->callback(item);
    }
}

/*
 * Go back (if submenu)
 */
void menu_back(void) {
    if (!current_menu) return;

    if (current_menu->parent) {
        menu_set(current_menu->parent);
    } else if (current_menu->on_back) {
        current_menu->on_back();
    }
}

/*
 * Draw menu
 */
void menu_draw(void) {
    if (!current_menu) return;

    fb_clear(1);  /* White background */

    /* Draw title if present */
    int y = MENU_MARGIN;
    if (current_menu->title) {
        font_draw_string(MENU_MARGIN, y, current_menu->title, 1);
        y += MENU_ITEM_HEIGHT + 2;
        fb_hline(0, y - 1, FB_WIDTH, 0);  /* Separator line */
    }

    /* Calculate visible items */
    int available_height = FB_HEIGHT - y - MENU_MARGIN;
    visible_items = available_height / MENU_ITEM_HEIGHT;

    /* Draw items */
    for (int i = 0; i < visible_items && (scroll_offset + i) < current_menu->item_count; i++) {
        int item_idx = scroll_offset + i;
        menu_item_t* item = &current_menu->items[item_idx];

        int item_y = y + i * MENU_ITEM_HEIGHT;

        /* Highlight selected item */
        if (item_idx == selected_index) {
            fb_fill_rect(0, item_y, FB_WIDTH, MENU_ITEM_HEIGHT, 0);
        }

        /* Draw item text */
        int color = (item_idx == selected_index) ? 0 : 1;
        text_draw_ellipsis(MENU_MARGIN, item_y + MENU_PADDING,
                          FB_WIDTH - MENU_MARGIN * 2, item->label, color);

        /* Draw indicator for submenus or checkboxes */
        if (item->type == MENU_ITEM_SUBMENU) {
            font_draw_char(FB_WIDTH - 10, item_y + MENU_PADDING, '>', color);
        } else if (item->type == MENU_ITEM_CHECKBOX) {
            font_draw_char(FB_WIDTH - 10, item_y + MENU_PADDING,
                          item->checked ? 'X' : ' ', color);
        }
    }

    /* Draw scroll indicators */
    if (scroll_offset > 0) {
        font_draw_char(FB_WIDTH - 10, y, '^', 1);
    }
    if (scroll_offset + visible_items < current_menu->item_count) {
        font_draw_char(FB_WIDTH - 10, FB_HEIGHT - MENU_ITEM_HEIGHT, 'v', 1);
    }
}

/*
 * Handle button press
 */
void menu_handle_button(int button) {
    switch (button) {
        case BUTTON_UP:
            menu_up();
            break;
        case BUTTON_DOWN:
            menu_down();
            break;
        case BUTTON_ENTER:
            menu_enter();
            break;
        case BUTTON_BACK:
            menu_back();
            break;
    }
}

/*
 * Create a simple menu from strings
 */
menu_t* menu_create(const char* title, const char** labels, int count,
                    menu_callback_t callback) {
    menu_t* menu = (menu_t*)heap_alloc(sizeof(menu_t));
    if (!menu) return NULL;

    menu->title = title;
    menu->item_count = count;
    menu->items = (menu_item_t*)heap_alloc(sizeof(menu_item_t) * count);
    menu->wrap = 1;
    menu->parent = NULL;
    menu->on_back = NULL;

    if (!menu->items) {
        heap_free(menu);
        return NULL;
    }

    for (int i = 0; i < count; i++) {
        menu->items[i].label = labels[i];
        menu->items[i].type = MENU_ITEM_ACTION;
        menu->items[i].callback = callback;
        menu->items[i].data = (void*)(intptr_t)i;
        menu->items[i].checked = 0;
    }

    return menu;
}

/*
 * Free menu
 */
void menu_destroy(menu_t* menu) {
    if (menu) {
        if (menu->items) {
            heap_free(menu->items);
        }
        heap_free(menu);
    }
}

/*
 * Get selected item
 */
menu_item_t* menu_get_selected_item(void) {
    if (!current_menu || current_menu->item_count == 0) return NULL;
    return &current_menu->items[selected_index];
}
