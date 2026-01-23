/*
 * PaperJam Bare-Metal OS - Renderer Header
 */

#ifndef RENDERER_H
#define RENDERER_H

#include "hal/bcm2837.h"
#include "sys/heap.h"
#include "gfx/text.h"

/* UI views */
typedef enum {
    UI_VIEW_MUSIC,
    UI_VIEW_MENU,
    UI_VIEW_BROWSE,
    UI_VIEW_SCREENSAVER
} ui_view_t;

/* Function prototypes */
void renderer_init(void);
void renderer_set_view(ui_view_t view);
ui_view_t renderer_get_view(void);
void renderer_invalidate(void);
void renderer_request_full_refresh(void);
void renderer_render(void);
void renderer_handle_button(int button);
void renderer_handle_long_press(int action);
void renderer_update(void);
void renderer_show_popup(const char* message, int duration_ms);
void renderer_show_volume(int volume);

#endif /* RENDERER_H */
