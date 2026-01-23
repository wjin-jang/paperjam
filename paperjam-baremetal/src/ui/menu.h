/*
 * PaperJam Bare-Metal OS - Menu System Header
 */

#ifndef MENU_H
#define MENU_H

#include "hal/bcm2837.h"

/* Forward declaration */
struct menu_item;

/* Menu item callback */
typedef void (*menu_callback_t)(struct menu_item* item);

/* Menu item types */
typedef enum {
    MENU_ITEM_ACTION,
    MENU_ITEM_SUBMENU,
    MENU_ITEM_CHECKBOX,
    MENU_ITEM_SEPARATOR
} menu_item_type_t;

/* Menu item */
typedef struct menu_item {
    const char* label;
    menu_item_type_t type;
    menu_callback_t callback;
    void* data;
    int checked;
} menu_item_t;

/* Menu */
typedef struct menu {
    const char* title;
    menu_item_t* items;
    int item_count;
    int wrap;
    struct menu* parent;
    void (*on_back)(void);
} menu_t;

/* Function prototypes */
void menu_init(void);
void menu_set(menu_t* menu);
menu_t* menu_get(void);
int menu_get_selected(void);
void menu_set_selected(int index);
void menu_up(void);
void menu_down(void);
void menu_enter(void);
void menu_back(void);
void menu_draw(void);
void menu_handle_button(int button);
menu_t* menu_create(const char* title, const char** labels, int count,
                    menu_callback_t callback);
void menu_destroy(menu_t* menu);
menu_item_t* menu_get_selected_item(void);

#endif /* MENU_H */
