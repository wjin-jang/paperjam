/*
 * PaperJam Bare-Metal OS - Button Driver Header
 */

#ifndef BUTTONS_H
#define BUTTONS_H

#include "hal/bcm2837.h"

/* Button IDs */
enum {
    BUTTON_PLAY_PAUSE = 0,
    BUTTON_PREV,
    BUTTON_NEXT,
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_ENTER,
    BUTTON_BACK,
    BUTTON_VOL_UP,
    BUTTON_VOL_DOWN,
    /* Long press actions */
    BUTTON_LONG_SHOW_QUEUE = 100,
    BUTTON_LONG_CONTEXT_MENU,
    BUTTON_LONG_HOME,
    BUTTON_LONG_SETTINGS,
    BUTTON_LONG_BROWSE,
};

/* Callback function type */
typedef void (*button_callback_t)(int button);

/* Function prototypes */
void buttons_init(void);
void buttons_poll(void);
int  buttons_is_pressed(int button);
int  buttons_any_pressed(void);
void buttons_set_press_callback(button_callback_t callback);
void buttons_set_release_callback(button_callback_t callback);
void buttons_set_long_press_callback(button_callback_t callback);
int  buttons_get_long_press_action(int button);
const char* buttons_get_name(int button);
int  buttons_wait_any(void);
void buttons_wait_release(int button);

#endif /* BUTTONS_H */
