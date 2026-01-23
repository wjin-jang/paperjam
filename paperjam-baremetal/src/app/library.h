/*
 * PaperJam Bare-Metal OS - Library Header
 */

#ifndef LIBRARY_H
#define LIBRARY_H

#include "hal/bcm2837.h"

/* Function prototypes */
void library_init(void);
int  library_scan(void);
int  library_count_entries(void);
const char* library_get_path(int index);
const char* library_get_title(int index);
const char* library_get_artist(int index);
const char* library_get_album(int index);
int  library_find_path(const char* path);
int  library_is_loaded(void);
void library_free(void);

#endif /* LIBRARY_H */
