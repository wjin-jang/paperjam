/*
 * PaperJam Bare-Metal OS - Favorites Header
 */

#ifndef FAVORITES_H
#define FAVORITES_H

#include "hal/bcm2837.h"

/* Function prototypes */
void favorites_init(void);
int  favorites_load(void);
int  favorites_save(void);
int  favorites_add(const char* path);
int  favorites_remove(const char* path);
int  favorites_toggle(const char* path);
int  favorites_is_favorite(const char* path);
int  favorites_count_entries(void);
const char* favorites_get_path(int index);
void favorites_clear(void);
void favorites_free(void);

#endif /* FAVORITES_H */
