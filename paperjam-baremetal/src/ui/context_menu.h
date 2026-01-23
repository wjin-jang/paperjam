/*
 * PaperJam Bare-Metal OS - Context Menu Header
 *
 * Popup context menus for track/album options
 */

#ifndef CONTEXT_MENU_H
#define CONTEXT_MENU_H

#include "hal/bcm2837.h"
#include "drivers/buttons.h"

/* Maximum menu items */
#define CONTEXT_MENU_MAX_ITEMS 8

/* Context menu item */
typedef struct {
    const char* label;
    void (*action)(void* data);
    void* data;
    int enabled;
} context_menu_item_t;

/* Context menu */
typedef struct {
    const char* title;
    context_menu_item_t items[CONTEXT_MENU_MAX_ITEMS];
    int item_count;
    int selected;
    int visible;
    int x, y;       /* Position (calculated automatically if -1) */
    int width;      /* Width (calculated automatically if 0) */
} context_menu_t;

/*
 * Initialize context menu system
 */
void context_menu_init(void);

/*
 * Create a new context menu
 */
context_menu_t* context_menu_create(const char* title);

/*
 * Add item to context menu
 *
 * Returns: Item index, or -1 on error
 */
int context_menu_add_item(context_menu_t* menu, const char* label,
                          void (*action)(void* data), void* data);

/*
 * Add separator to context menu
 */
void context_menu_add_separator(context_menu_t* menu);

/*
 * Enable/disable an item
 */
void context_menu_set_enabled(context_menu_t* menu, int index, int enabled);

/*
 * Show context menu at position (or centered if x,y = -1)
 */
void context_menu_show(context_menu_t* menu, int x, int y);

/*
 * Hide and destroy context menu
 */
void context_menu_hide(void);

/*
 * Check if context menu is visible
 */
int context_menu_is_visible(void);

/*
 * Handle button press (returns 1 if consumed)
 */
int context_menu_handle_button(int button);

/*
 * Draw context menu
 */
void context_menu_draw(void);

/*
 * Destroy context menu
 */
void context_menu_destroy(context_menu_t* menu);

/*
 * Get currently active context menu
 */
context_menu_t* context_menu_get_active(void);

/* Common context menu builders */

/*
 * Create track context menu
 *
 * path: Path to the track file
 */
context_menu_t* context_menu_create_track(const char* path);

/*
 * Create queue context menu
 *
 * queue_index: Index in the queue
 */
context_menu_t* context_menu_create_queue_item(int queue_index);

#endif /* CONTEXT_MENU_H */
