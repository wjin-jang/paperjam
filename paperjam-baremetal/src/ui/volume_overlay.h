/*
 * PaperJam Bare-Metal OS - Volume Overlay Header
 */

#ifndef VOLUME_OVERLAY_H
#define VOLUME_OVERLAY_H

#include "hal/bcm2837.h"
#include "sys/heap.h"

/* Function prototypes */
void volume_overlay_init(void);
void volume_overlay_show(int volume);
void volume_overlay_hide(void);
void volume_overlay_draw(void);
void volume_overlay_update(void);
int  volume_overlay_is_visible(void);
void volume_overlay_cleanup(void);

#endif /* VOLUME_OVERLAY_H */
