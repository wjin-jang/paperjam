/*
 * PaperJam Bare-Metal OS - Icons Header
 *
 * Bitmap icons for UI elements
 */

#ifndef ICONS_H
#define ICONS_H

#include "hal/bcm2837.h"

/* Icon size */
#define ICON_SIZE 16

/* Icon indices */
typedef enum {
    ICON_PLAY,
    ICON_PAUSE,
    ICON_STOP,
    ICON_PREV,
    ICON_NEXT,
    ICON_REPEAT,
    ICON_REPEAT_ONE,
    ICON_SHUFFLE,
    ICON_VOLUME,
    ICON_VOLUME_MUTE,
    ICON_FOLDER,
    ICON_FILE,
    ICON_MUSIC,
    ICON_HEART,
    ICON_HEART_OUTLINE,
    ICON_SETTINGS,
    ICON_BATTERY_FULL,
    ICON_BATTERY_HALF,
    ICON_BATTERY_LOW,
    ICON_BATTERY_EMPTY,
    ICON_BATTERY_CHARGING,
    ICON_CHECK,
    ICON_ARROW_RIGHT,
    ICON_ARROW_UP,
    ICON_ARROW_DOWN,
    ICON_COUNT
} icon_id_t;

/*
 * Initialize icons module
 */
void icons_init(void);

/*
 * Draw an icon at specified position
 *
 * x, y: Top-left position
 * icon: Icon ID to draw
 * color: 1 = white (clear), 0 = black (set)
 */
void icon_draw(int x, int y, icon_id_t icon, int color);

/*
 * Draw an icon centered in a region
 */
void icon_draw_centered(int x, int y, int w, int h, icon_id_t icon, int color);

/*
 * Get icon bitmap data
 *
 * Returns pointer to 16x16 bit array (32 bytes, 2 bytes per row)
 */
const u8* icon_get_data(icon_id_t icon);

#endif /* ICONS_H */
