/*
 * PaperJam Bare-Metal OS - Browse View Header
 */

#ifndef BROWSE_VIEW_H
#define BROWSE_VIEW_H

#include "hal/bcm2837.h"
#include "drivers/buttons.h"

/* Browse modes */
#define BROWSE_FOLDERS  0
#define BROWSE_ARTISTS  1
#define BROWSE_ALBUMS   2
#define BROWSE_TRACKS   3

/* Function prototypes */
void browse_view_init(void);
void browse_view_set_mode(int mode);
void browse_view_refresh(void);
void browse_view_go_up(void);
void browse_view_handle_button(int button);
void browse_view_draw(void);
const char* browse_view_get_path(void);
void browse_view_cleanup(void);

#endif /* BROWSE_VIEW_H */
