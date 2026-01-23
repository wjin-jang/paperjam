/*
 * PaperJam Bare-Metal OS - Music View Header
 */

#ifndef MUSIC_VIEW_H
#define MUSIC_VIEW_H

#include "hal/bcm2837.h"
#include "hal/timer.h"

/* View modes */
typedef enum {
    MUSIC_VIEW_NOW_PLAYING,
    MUSIC_VIEW_BROWSE,
    MUSIC_VIEW_QUEUE
} music_view_mode_t;

/* Function prototypes */
void music_view_init(void);
void music_view_set_mode(music_view_mode_t mode);
music_view_mode_t music_view_get_mode(void);
void music_view_update_metadata(void);
void music_view_draw(void);
void music_view_handle_button(int button);
void music_view_update(void);

#endif /* MUSIC_VIEW_H */
