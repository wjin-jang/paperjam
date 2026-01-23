/*
 * PaperJam Bare-Metal OS - GPIO Button Driver
 *
 * Button pins with pull-up resistors, active low
 * | Pin | Action     | Long Press   |
 * |-----|------------|--------------|
 * |  4  | play_pause | show_queue   |
 * |  5  | prev       | settings     |
 * |  6  | next       | browse       |
 * | 12  | up         | -            |
 * | 13  | down       | -            |
 * | 16  | enter      | context_menu |
 * | 19  | back       | home         |
 * | 20  | vol_up     | - (repeat)   |
 * | 21  | vol_down   | - (repeat)   |
 */

#include "hal/bcm2837.h"
#include "hal/gpio.h"
#include "hal/timer.h"
#include "buttons.h"

/* Button configuration */
static const int button_pins[] = { 4, 5, 6, 12, 13, 16, 19, 20, 21 };
#define NUM_BUTTONS (sizeof(button_pins) / sizeof(button_pins[0]))

/* Debounce and long press timing */
#define DEBOUNCE_MS         50
#define LONG_PRESS_MS       500
#define REPEAT_DELAY_MS     400
#define REPEAT_RATE_MS      100

/* Button state */
typedef struct {
    u8 pin;
    u8 pressed;
    u8 was_pressed;
    u8 long_press_fired;
    u64 press_time;
    u64 last_repeat;
} button_state_t;

static button_state_t button_states[NUM_BUTTONS];

/* Callback functions */
static button_callback_t on_press_callback = NULL;
static button_callback_t on_release_callback = NULL;
static button_callback_t on_long_press_callback = NULL;

/*
 * Initialize buttons
 */
void buttons_init(void) {
    for (int i = 0; i < (int)NUM_BUTTONS; i++) {
        int pin = button_pins[i];
        gpio_input_pullup(pin);

        button_states[i].pin = pin;
        button_states[i].pressed = 0;
        button_states[i].was_pressed = 0;
        button_states[i].long_press_fired = 0;
        button_states[i].press_time = 0;
        button_states[i].last_repeat = 0;
    }
}

/*
 * Get button ID from pin
 */
static int pin_to_button(int pin) {
    switch (pin) {
        case 4:  return BUTTON_PLAY_PAUSE;
        case 5:  return BUTTON_PREV;
        case 6:  return BUTTON_NEXT;
        case 12: return BUTTON_UP;
        case 13: return BUTTON_DOWN;
        case 16: return BUTTON_ENTER;
        case 19: return BUTTON_BACK;
        case 20: return BUTTON_VOL_UP;
        case 21: return BUTTON_VOL_DOWN;
        default: return -1;
    }
}

/*
 * Check if a button has long press action
 */
static int has_long_press(int button) {
    return button == BUTTON_PLAY_PAUSE ||
           button == BUTTON_ENTER ||
           button == BUTTON_BACK ||
           button == BUTTON_PREV ||
           button == BUTTON_NEXT;
}

/*
 * Get long press action for a button
 *
 * Long press mappings:
 *   PLAY/PAUSE -> Show queue
 *   ENTER      -> Context menu
 *   BACK       -> Home (now playing)
 *   PREV       -> Settings
 *   NEXT       -> Browse folders
 */
int buttons_get_long_press_action(int button) {
    switch (button) {
        case BUTTON_PLAY_PAUSE: return BUTTON_LONG_SHOW_QUEUE;
        case BUTTON_ENTER:      return BUTTON_LONG_CONTEXT_MENU;
        case BUTTON_BACK:       return BUTTON_LONG_HOME;
        case BUTTON_PREV:       return BUTTON_LONG_SETTINGS;
        case BUTTON_NEXT:       return BUTTON_LONG_BROWSE;
        default:                return -1;
    }
}

/*
 * Poll buttons (call frequently from main loop)
 */
void buttons_poll(void) {
    u64 now = timer_get_ms();

    for (int i = 0; i < (int)NUM_BUTTONS; i++) {
        button_state_t* state = &button_states[i];
        int button = pin_to_button(state->pin);
        int raw_pressed = !gpio_read(state->pin);  /* Active low */

        /* Debounce */
        if (raw_pressed != state->pressed) {
            if (now - state->press_time > DEBOUNCE_MS) {
                state->pressed = raw_pressed;

                if (state->pressed) {
                    /* Button pressed */
                    state->press_time = now;
                    state->long_press_fired = 0;
                    state->last_repeat = now;

                    /* Fire press callback for buttons without long press */
                    if (!has_long_press(button) && on_press_callback) {
                        on_press_callback(button);
                    }
                } else {
                    /* Button released */
                    if (!state->long_press_fired) {
                        /* Short press */
                        if (has_long_press(button) && on_press_callback) {
                            on_press_callback(button);
                        }
                    }
                    if (on_release_callback) {
                        on_release_callback(button);
                    }
                }
            }
        }

        /* Check for long press */
        if (state->pressed && !state->long_press_fired && has_long_press(button)) {
            if (now - state->press_time >= LONG_PRESS_MS) {
                state->long_press_fired = 1;
                if (on_long_press_callback) {
                    on_long_press_callback(buttons_get_long_press_action(button));
                }
            }
        }

        /* Check for repeat (for volume and navigation) */
        if (state->pressed && !has_long_press(button)) {
            if (button == BUTTON_VOL_UP || button == BUTTON_VOL_DOWN ||
                button == BUTTON_UP || button == BUTTON_DOWN) {
                u64 delay = (state->last_repeat == state->press_time) ?
                            REPEAT_DELAY_MS : REPEAT_RATE_MS;
                if (now - state->last_repeat >= delay) {
                    state->last_repeat = now;
                    if (on_press_callback) {
                        on_press_callback(button);
                    }
                }
            }
        }

        state->was_pressed = state->pressed;
    }
}

/*
 * Check if a specific button is pressed
 */
int buttons_is_pressed(int button) {
    for (int i = 0; i < (int)NUM_BUTTONS; i++) {
        if (pin_to_button(button_states[i].pin) == button) {
            return button_states[i].pressed;
        }
    }
    return 0;
}

/*
 * Check if any button is pressed
 */
int buttons_any_pressed(void) {
    for (int i = 0; i < (int)NUM_BUTTONS; i++) {
        if (button_states[i].pressed) {
            return 1;
        }
    }
    return 0;
}

/*
 * Set callback for button press
 */
void buttons_set_press_callback(button_callback_t callback) {
    on_press_callback = callback;
}

/*
 * Set callback for button release
 */
void buttons_set_release_callback(button_callback_t callback) {
    on_release_callback = callback;
}

/*
 * Set callback for long press
 */
void buttons_set_long_press_callback(button_callback_t callback) {
    on_long_press_callback = callback;
}

/*
 * Get button name string
 */
const char* buttons_get_name(int button) {
    switch (button) {
        case BUTTON_PLAY_PAUSE: return "PLAY";
        case BUTTON_PREV:       return "PREV";
        case BUTTON_NEXT:       return "NEXT";
        case BUTTON_UP:         return "UP";
        case BUTTON_DOWN:       return "DOWN";
        case BUTTON_ENTER:      return "ENTER";
        case BUTTON_BACK:       return "BACK";
        case BUTTON_VOL_UP:     return "VOL+";
        case BUTTON_VOL_DOWN:   return "VOL-";
        case BUTTON_LONG_SHOW_QUEUE:   return "QUEUE";
        case BUTTON_LONG_CONTEXT_MENU: return "MENU";
        case BUTTON_LONG_HOME:         return "HOME";
        case BUTTON_LONG_SETTINGS:     return "SETTINGS";
        case BUTTON_LONG_BROWSE:       return "BROWSE";
        default:                return "?";
    }
}

/*
 * Wait for any button press (blocking)
 */
int buttons_wait_any(void) {
    while (!buttons_any_pressed()) {
        buttons_poll();
        timer_delay_ms(10);
    }

    for (int i = 0; i < (int)NUM_BUTTONS; i++) {
        if (button_states[i].pressed) {
            return pin_to_button(button_states[i].pin);
        }
    }
    return -1;
}

/*
 * Wait for specific button release
 */
void buttons_wait_release(int button) {
    while (buttons_is_pressed(button)) {
        buttons_poll();
        timer_delay_ms(10);
    }
}
