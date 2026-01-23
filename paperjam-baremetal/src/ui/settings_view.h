/*
 * PaperJam Bare-Metal OS - Settings View Header
 */

#ifndef SETTINGS_VIEW_H
#define SETTINGS_VIEW_H

#include "hal/bcm2837.h"
#include "drivers/buttons.h"

/*
 * Initialize settings view
 */
void settings_view_init(void);

/*
 * Enter settings view
 */
void settings_view_enter(void);

/*
 * Exit settings view
 */
void settings_view_exit(void);

/*
 * Check if settings view is active
 */
int settings_view_is_active(void);

/*
 * Handle button press (returns 1 if consumed)
 */
int settings_view_handle_button(int button);

/*
 * Draw settings view
 */
void settings_view_draw(void);

#endif /* SETTINGS_VIEW_H */
