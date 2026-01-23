/*
 * PaperJam Bare-Metal OS - Screensaver Header
 */

#ifndef SCREENSAVER_H
#define SCREENSAVER_H

#include "hal/bcm2837.h"

/* Function prototypes */
void screensaver_init(void);
void screensaver_reset(void);
int  screensaver_should_activate(void);
void screensaver_activate(void);
void screensaver_deactivate(void);
int  screensaver_is_active(void);
void screensaver_draw(void);
void screensaver_update(void);
void screensaver_set_timeout(u32 timeout_ms);
u32  screensaver_get_timeout(void);

#endif /* SCREENSAVER_H */
