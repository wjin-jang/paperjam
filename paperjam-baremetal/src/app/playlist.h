/*
 * PaperJam Bare-Metal OS - Playlist Header
 */

#ifndef PLAYLIST_H
#define PLAYLIST_H

#include "hal/bcm2837.h"
#include "hal/timer.h"

/* Function prototypes */
void queue_init(void);
void queue_clear(void);
int  queue_add(const char* path);
int  queue_add_next(const char* path);    /* Add after current track */
int  queue_insert(int index, const char* path);  /* Insert at position */
int  queue_remove(int index);
int  queue_move(int from, int to);
int  queue_count(void);
const char* queue_get(int index);         /* Alias for queue_get_path */
const char* queue_get_path(int index);
int  queue_get_current(void);             /* Get current track index */
void queue_set_current(int index);        /* Set current track index */
void queue_add_all(void);
void queue_shuffle(void);
int  queue_save(const char* filename);
int  queue_load(const char* filename);
void queue_free(void);

#endif /* PLAYLIST_H */
